""" Title: COVID Airborne Risk Assessment
Author: <author(s) names>
Date: <date>
Code version: <code version>
Availability: <where it's located> """

from cara.models import ExposureModel, InfectedPopulation
from cara import model_scenarios_paper
from cara.results_paper import *
from cara.test_plots import *
from cara.monte_carlo.data import symptomatic_vl_frequencies
from itertools import product
from dataclasses import dataclass

# Exhaled virions while talking, seated #
#print('\n<<<<<<<<<<< Vlout for Talking, seated >>>>>>>>>>>')
#exposure_model_from_vl_talking()

# Exhaled virions while breathing, seated #
#print('\n<<<<<<<<<<< Vlout for Breathing, seated >>>>>>>>>>>')
#exposure_model_from_vl_breathing()

# Exhaled virions while breathing, light activity #
#print('\n<<<<<<<<<<< Vlout for Shouting, light activity >>>>>>>>>>>')
#exposure_model_from_vl_shouting()

# Exhaled virions while talking according to BLO model, seated #
#print('\n<<<<<<<<<<< Vlout for Talking, seated with chosen Cn,L >>>>>>>>>>>')
#exposure_model_from_vl_talking_cn()

# Exhaled virions while breathing according to BLO model, seated #
#print('\n<<<<<<<<<<< Vlout for Breathing, seated with chosen Cn,B >>>>>>>>>>>')
#exposure_model_from_vl_breathing_cn()
#print('\n')

############ Plots with viral loads and emission rates + statistical data ############
#present_vl_er_histograms(activity='Seated', mask='No mask')
#present_vl_er_histograms(activity='Light activity', mask='No mask')
#present_vl_er_histograms(activity='Heavy exercise', mask='No mask')

############ CDFs for comparing the QR-Values in different scenarios ############
#generate_cdf_curves()

############ Deposition Fraction Graph ############
#print('\n<<<<<<<<<<< Deposition Fraction for Breathing, seated >>>>>>>>>>>') 
#calculate_deposition_factor()

############ Comparison between concentration curves ############ 
# compare_concentration_curves_virus([classroom_model_IGH_no_mask_windows_closed[0],classroom_model_IGH_no_mask_windows_open_breaks[0],
#                              classroom_model_IGH_no_mask_windows_open_alltimes[0]],
#                             labels=['Windows closed', 'Window open during breaks', 'Window open at all times'],
#                             colors=['tomato', 'lightskyblue', 'limegreen', '#1f77b4', 'seagreen', 'lightskyblue', 'deepskyblue'],
#                             title='No mask - Spring/Summer period'
#                             )
# print_qd_info(classroom_model_IGH_no_mask_windows_closed[0])
# print_qd_info(classroom_model_IGH_no_mask_windows_open_breaks[0])
# print_qd_info(classroom_model_IGH_no_mask_windows_open_alltimes[0])
compare_concentration_curves()

############ Used for testing ############
#exposure_model_from_vl_talking_new_points()
