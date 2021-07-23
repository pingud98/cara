import concurrent.futures
import base64
import dataclasses
from datetime import datetime, timedelta
import io
import typing
import urllib
import zlib

import loky
import jinja2
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import numpy as np
import qrcode

from cara import models
from ... import monte_carlo as mc
from .model_generator import FormData, _DEFAULT_MC_SAMPLE_SIZE
from ... import dataclass_utils


def model_start_end(model: models.ExposureModel):
    t_start = min(model.exposed.presence.boundaries()[0][0],
                  model.concentration_model.infected.presence.boundaries()[0][0])
    t_end = max(model.exposed.presence.boundaries()[-1][1],
                model.concentration_model.infected.presence.boundaries()[-1][1])
    return t_start, t_end


def calculate_report_data(model: models.ExposureModel):
    resolution = 600

    t_start, t_end = model_start_end(model)
    times = list(np.linspace(t_start, t_end, resolution))
    concentrations = [np.mean(model.concentration_model.concentration(time))
                      for time in times]
    highest_const = max(concentrations)
    prob = np.mean(model.infection_probability())
    er = np.mean(model.concentration_model.infected.emission_rate_when_present())
    exposed_occupants = model.exposed.number
    expected_new_cases = np.mean(model.expected_new_cases())

    return {
        "times": times,
        "concentrations": concentrations,
        "highest_const": highest_const,
        "prob_inf": prob,
        "emission_rate": er,
        "exposed_occupants": exposed_occupants,
        "expected_new_cases": expected_new_cases,
        "scenario_plot_src": img2base64(_figure2bytes(plot(times, concentrations, model))),
    }


def generate_qr_code(base_url, calculator_prefix, form: FormData):
    form_dict = FormData.to_dict(form, strip_defaults=True)

    # Generate the calculator URL arguments that would be needed to re-create this
    # form.
    args = urllib.parse.urlencode(form_dict)

    # Then zlib compress + base64 encode the string. To be inverted by the
    # /_c/ endpoint.
    compressed_args = base64.b64encode(zlib.compress(args.encode())).decode()
    qr_url = f"{base_url}/_c/{compressed_args}"
    url = f"{base_url}{calculator_prefix}?{args}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    return {
        'image': img2base64(_img2bytes(img)),
        'link': url,
        'qr_url': qr_url,
    }


def _img2bytes(figure):
    # Draw the image
    img_data = io.BytesIO()
    figure.save(img_data, format='png', bbox_inches="tight")
    return img_data


def _figure2bytes(figure):
    # Draw the image
    img_data = io.BytesIO()
    figure.savefig(img_data, format='png', bbox_inches="tight")
    return img_data


def img2base64(img_data) -> str:
    plt.close()
    img_data.seek(0)
    pic_hash = base64.b64encode(img_data.read()).decode('ascii')
    # A src suitable for a tag such as f'<img id="scenario_concentration_plot" src="{result}">.
    return f'data:image/png;base64,{pic_hash}'

def plot(times, concentrations, model: models.ExposureModel):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    datetimes = [datetime(1970, 1, 1) + timedelta(hours=time) for time in times]
    
    #Concentration as mean viral concentration (virion m$^{-3}$)
    concentrations = [c * model.concentration_model.virus.quantum_infectious_dose for c in concentrations]
    
    ax.plot(datetimes, concentrations, lw=2, color='#1f77b4', label='Mean viral concentration')
    ax.spines['right'].set_visible(False)

    ax.set_xlabel('Time of day', fontsize=14)
    ax.set_ylabel('Mean viral concentration\n(virion m$^{-3}$)', fontsize=14)
    ax.set_title('Concentration profile')
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))

    # Plot presence of exposed person
    for i, (presence_start, presence_finish) in enumerate(model.exposed.presence.boundaries()):
        ax.fill_between(
            datetimes, concentrations, 0,
            where=(np.array(times) > presence_start) & (np.array(times) < presence_finish),
            color="#1f77b4", alpha=0.1,
            label="Presence of exposed person(s)" if i == 0 else ""
        )

    #See CERN-OPEN-2021-004, p. 15, eq. 16. - Cumulative Dose
    cumulated_exposure = model.cumulated_exposure()
    present_indexes = np.array([model.exposed.person_present(t) for t in times])
    modified_concentrations = np.array(concentrations)
    modified_concentrations[~present_indexes] = 0
    
    qds = [np.trapz(modified_concentrations[:i + 1], times[:i + 1]) * factor for i in range(len(times))]
    
    ax1 = ax.twinx()
    ax1.plot(datetimes, cumulated_exposure, label='Mean cumulative dose', color='#1f77b4', linestyle='dotted')
    ax1.spines["right"].set_linestyle("--")
    ax1.spines["right"].set_linestyle((0,(1,5)))
    ax1.set_ylabel('Mean cumulative dose\n(virion)', fontsize=14)
    ax1.set_ylim(ax1.get_ylim()[0], ax1.get_ylim()[1])
    ax1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))

    # Place a legend outside of the axes itself.
    ax_handles, ax_labels = ax.get_legend_handles_labels()
    ax1_handles, ax1_labels = ax1.get_legend_handles_labels()
    handles = ax_handles + ax1_handles
    labels = ax_labels + ax1_labels
    order = [0, 2, 1] # 0 - Mean viral concentration   1 - Presence of exposed person(s)    2 - Mean cumulative dose 
    fig.legend(handles = [handles[idx] for idx in order], labels = [labels[idx] for idx in order], bbox_to_anchor=(1.05, 0.9), loc='upper left')
    ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1])
    # Remove top spines
    ax.spines['top'].set_visible(False)
    ax1.spines['top'].set_visible(False)

    return fig

def minutes_to_time(minutes: int) -> str:
    minute_string = str(minutes % 60)
    minute_string = "0" * (2 - len(minute_string)) + minute_string
    hour_string = str(minutes // 60)
    hour_string = "0" * (2 - len(hour_string)) + hour_string

    return f"{hour_string}:{minute_string}"


def readable_minutes(minutes: int) -> str:
    time = float(minutes)
    unit = " minute"
    if time % 60 == 0:
        time = minutes/60
        unit = " hour"
    if time != 1:
        unit += "s"

    if time.is_integer():
        time_str = "{:0.0f}".format(time)
    else:
        time_str = "{0:.2f}".format(time)

    return time_str + unit


def non_zero_percentage(percentage: int) -> str:
    if percentage < 0.01:
        return "<0.01%"
    elif percentage < 1:
        return "{:0.2f}%".format(percentage)
    else:
        return "{:0.1f}%".format(percentage)


def manufacture_alternative_scenarios(form: FormData) -> typing.Dict[str, mc.ExposureModel]:
    scenarios = {}

    # Two special option cases - HEPA and/or FFP2 masks.
    FFP2_being_worn = bool(form.mask_wearing_option == 'mask_on' and form.mask_type == 'FFP2')
    if FFP2_being_worn and form.hepa_option:
        FFP2andHEPAalternative = dataclass_utils.replace(form, mask_type='Type I')
        scenarios['Base scenario with HEPA filter and Type I masks'] = FFP2andHEPAalternative.build_mc_model()
    if not FFP2_being_worn and form.hepa_option:
        noHEPAalternative = dataclass_utils.replace(form, mask_type = 'FFP2')
        noHEPAalternative = dataclass_utils.replace(noHEPAalternative, mask_wearing_option = 'mask_on')
        noHEPAalternative = dataclass_utils.replace(noHEPAalternative, hepa_option=False)
        scenarios['Base scenario without HEPA filter, with FFP2 masks'] = noHEPAalternative.build_mc_model()

    # The remaining scenarios are based on Type I masks (possibly not worn)
    # and no HEPA filtration.
    form = dataclass_utils.replace(form, mask_type='Type I')
    if form.hepa_option:
        form = dataclass_utils.replace(form, hepa_option=False)

    with_mask = dataclass_utils.replace(form, mask_wearing_option='mask_on')
    without_mask = dataclass_utils.replace(form, mask_wearing_option='mask_off')

    if form.ventilation_type == 'mechanical_ventilation':
        #scenarios['Mechanical ventilation with Type I masks'] = with_mask.build_mc_model()
        scenarios['Mechanical ventilation without masks'] = without_mask.build_mc_model()

    elif form.ventilation_type == 'natural_ventilation':
        #scenarios['Windows open with Type I masks'] = with_mask.build_mc_model()
        scenarios['Windows open without masks'] = without_mask.build_mc_model()

    # No matter the ventilation scheme, we include scenarios which don't have any ventilation.
    with_mask_no_vent = dataclass_utils.replace(with_mask, ventilation_type='no_ventilation')
    without_mask_or_vent = dataclass_utils.replace(without_mask, ventilation_type='no_ventilation')
    scenarios['No ventilation with Type I masks'] = with_mask_no_vent.build_mc_model()
    scenarios['Neither ventilation nor masks'] = without_mask_or_vent.build_mc_model()

    return scenarios


def comparison_plot(scenarios: typing.Dict[str, dict], sample_times: np.ndarray):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax1 = ax.twinx()

    dash_styled_scenarios = [
        'Base scenario with FFP2 masks',
        'Base scenario with HEPA filter',
        'Base scenario with HEPA and FFP2 masks',
    ]

    datetimes = [datetime(1970, 1, 1) + timedelta(hours=time) for time in sample_times]

    for name, statistics in scenarios.items():
        model = statistics['model']
        concentrations = statistics['concentrations']

        #See CERN-OPEN-2021-004, p. 15, eq. 16. - Cumulative Dose
        factor = 0.6 * np.mean(model.exposed.activity.inhalation_rate) * (1 - model.exposed.mask.η_inhale)
        present_indexes = np.array([model.exposed.person_present(t) for t in sample_times])

        modified_concentrations = np.array(concentrations)
        modified_concentrations[~present_indexes] = 0
        qds = [np.trapz(modified_concentrations[:i + 1], sample_times[:i + 1]) * factor for i in range(len(sample_times))]  
        
        # Plot concentrations and cumulative dose
        if name in dash_styled_scenarios:
            ax.plot(datetimes, concentrations, label=name, linestyle='--')
            ax1.plot(datetimes, qds, label=f'Mean cumulative dose:\n{name}', linestyle='dotted')
        else:
            ax.plot(datetimes, concentrations, label=name, linestyle='-', alpha=0.5)
            ax1.plot(datetimes, qds, label=f'Mean cumulative dose:\n{name}', linestyle='dotted', alpha=0.5)
        
 
    # Place a legend outside of the axes itself.
    fig.legend(bbox_to_anchor=(1.05, 0.95), loc='upper left')
    
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.set_xlabel('Time of day', fontsize=14)
    ax.set_ylabel('Mean viral concentration\n(virion m$^{-3}$)', fontsize=14)
    ax.set_title('Concentration profile')
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))

    ax1.spines['top'].set_visible(False)
    ax1.spines["right"].set_linestyle("--")
    ax1.spines["right"].set_linestyle((0,(1,5)))
    ax1.set_ylabel('Mean cumulative dose\n(virion)', fontsize=14)
    ax1.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))

    return fig


def scenario_statistics(mc_model: mc.ExposureModel, sample_times: np.ndarray):
    model = mc_model.build_model(size=_DEFAULT_MC_SAMPLE_SIZE)
    return {
        'model': model,
        'probability_of_infection': np.mean(model.infection_probability()),
        'expected_new_cases': np.mean(model.expected_new_cases()),
        'concentrations': [
            np.mean(model.concentration_model.concentration(time)) * model.concentration_model.virus.quantum_infectious_dose
            for time in sample_times
        ],
    }


def comparison_report(
        scenarios: typing.Dict[str, mc.ExposureModel],
        sample_times: np.ndarray,
        executor_factory: typing.Callable[[], concurrent.futures.Executor],
):
    statistics = {}
    with executor_factory() as executor:
        results = executor.map(
            scenario_statistics,
            scenarios.values(),
            [sample_times] * len(scenarios),
            timeout=60,
        )

    for (name, model), model_stats in zip(scenarios.items(), results):
        statistics[name] = model_stats
    return {
        'plot': img2base64(_figure2bytes(comparison_plot(statistics, sample_times))),
        'stats': statistics,
    }


@dataclasses.dataclass
class ReportGenerator:
    jinja_loader: jinja2.BaseLoader
    calculator_prefix: str

    def build_report(
            self,
            base_url: str,
            form: FormData,
            executor_factory: typing.Callable[[], concurrent.futures.Executor],
    ) -> str:
        model = form.build_model()
        context = self.prepare_context(base_url, model, form, executor_factory=executor_factory)
        return self.render(context)

    def prepare_context(
            self,
            base_url: str,
            model: models.ExposureModel,
            form: FormData,
            executor_factory: typing.Callable[[], concurrent.futures.Executor],
    ) -> dict:
        now = datetime.utcnow().astimezone()
        time = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        context = {
            'model': model,
            'form': form,
            'creation_date': time,
        }

        t_start, t_end = model_start_end(model)
        scenario_sample_times = np.linspace(t_start, t_end, 350)

        context.update(calculate_report_data(model))
        alternative_scenarios = manufacture_alternative_scenarios(form)
        context['alternative_scenarios'] = comparison_report(
            alternative_scenarios, scenario_sample_times, executor_factory=executor_factory,
        )
        context['qr_code'] = generate_qr_code(base_url, self.calculator_prefix, form)
        context['calculator_prefix'] = self.calculator_prefix
        context['scale_warning'] = {
            'level': 'Yellow - 2', 
            'incidence_rate': 'lower than 25 new cases per 100 000 inhabitants',
            'onsite_access': 'of about 8000', 
            'threshold' : ''
        } 
        return context

    def _template_environment(self) -> jinja2.Environment:
        env = jinja2.Environment(
            loader=self.jinja_loader,
            undefined=jinja2.StrictUndefined,
        )
        env.filters['non_zero_percentage'] = non_zero_percentage
        env.filters['readable_minutes'] = readable_minutes
        env.filters['minutes_to_time'] = minutes_to_time
        env.filters['float_format'] = "{0:.2f}".format
        env.filters['int_format'] = "{:0.0f}".format
        return env

    def render(self, context: dict) -> str:
        template = self._template_environment().get_template("calculator.report.html.j2")
        return template.render(**context)
