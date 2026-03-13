# -*- coding: utf-8 -*-
"""
Created on Fri Jan 24 16:12:34 2025

@author: andre
"""

# ==========================================================
# Pyomo Translation of ec.mod
# ==========================================================

import pyomo.environ as pyo

# ----------------------------------------------------------
# 1. Abstract model initialization
# ----------------------------------------------------------

model = pyo.AbstractModel()

# ----------------------------------------------------------
# 2. Fundamental Elements
# ----------------------------------------------------------

# >>> Time periods:
model.nT = pyo.Param(within=pyo.PositiveIntegers)       # number of time periods
model.T = pyo.RangeSet(1, model.nT)                 # set of time periods
model.T0 = pyo.RangeSet(0, model.nT)                # T union {0}

# >>> Intraday markets:
model.nIM = pyo.Param(within=pyo.PositiveIntegers)      # number of intraday markets
model.IM = pyo.RangeSet(1, model.nIM)               # set of intraday markets

# For sets of time periods in each intraday market:
model.TIM = pyo.Set(model.IM, ordered=True)          # time periods in IM "i"
model.IMT = pyo.Set(model.T, ordered=True)           # intraday markets that include time "t"
model.sgim = pyo.Param(model.IM, within=pyo.PositiveIntegers)   # stage associated to each IM "i"

# >>> Scenario tree and Electricity market parameters:
model.nS = pyo.Param(within=pyo.NonNegativeIntegers)     # num. of scenarios
model.nSG = pyo.Param(within=pyo.NonNegativeIntegers)    # num. of stages

# Full scenario set and preserved set
model.S0 = pyo.RangeSet(1, model.nS)                 # complete set of scenarios
model.S = pyo.Set(within=model.S0, ordered=True)      # preserved scenario (Prob>0) 
# We could have put mutable = True and define it after creating the instance but it would have been uncorrect as S is then used to define other sets

# Stage sets
model.SG = pyo.RangeSet(1, model.nSG)
model.SG0 = pyo.Set(initialize=lambda m: [0] + list(range(1, pyo.value(m.nSG)+1)), ordered=True)

# Scenario clusters c {SG0, S0}: # In Pyomo, we can define this as a two-dimensional set: 
def c_init(model, sg, s): # Then I will modify this cluster after creating the instance in ec_run.py
    return sorted(set())
model.c = pyo.Set(model.SG0, model.S0, initialize=c_init, within=model.S0)

model.nRVSG = pyo.Param(model.SG, within=pyo.NonNegativeIntegers, default=0) # Number of random variables at each stage
model.nRV = pyo.Param(initialize=lambda model: sum(model.nRVSG[sg] for sg in model.SG)) # total number of random variables = sum of nRVSG
model.fRVSG = pyo.Param(model.SG, initialize=lambda model, i: 1 + sum(model.nRVSG[sg] for sg in range(1, i))) # fRVSG = index of first RV of each stage

# Probabilities and random variables
model.Prob0 = pyo.Param(model.S0)       # scenario's probabilities (including zero values)
model.Prob  = pyo.Param(model.S)        # preserved scenario probabilities

# Complete and preserved scenario sets
model.Scen0 = pyo.Param(pyo.RangeSet(1, model.nRV), model.S0, within=pyo.Reals, default=0.0)
model.Scen = pyo.Param(pyo.RangeSet(1, model.nRV), model.S, within=pyo.Reals, default=0.0)

# ----------------------------------------------------------
# 3. Flexible Demand
# ----------------------------------------------------------

# Sets
model.nFI = pyo.Param(within=pyo.NonNegativeIntegers)   # set of time intervals where a fraction of demand cf has to be met.
model.FI = pyo.RangeSet(1, model.nFI)                   # set of intervals for demand

# # Operational Parameters
model.FD   = pyo.Param(model.T, within=pyo.NonNegativeReals)   # Central demand [MWh]
model.FD_L = pyo.Param(model.T, within=pyo.NonNegativeReals)   # Lower bound on flexible demand
model.FD_U = pyo.Param(model.T, within=pyo.NonNegativeReals)   # Upper bound on flexible demand
model.TF_L = pyo.Param(model.FI, within=pyo.PositiveIntegers)  # First time step of interval
model.TF_U = pyo.Param(model.FI, within=pyo.PositiveIntegers)  # Last time step of interval
model.coef_FD = pyo.Param(model.FI, within=pyo.Reals)          # fraction of central demand that must be met
model.C_FD = pyo.Param(within=pyo.Reals)                       # cost per unit of flexible demand
model.RUFD = pyo.Param(model.T, within=pyo.NonNegativeReals)   # Upwards reserve limit for FD
model.RDFD = pyo.Param(model.T, within=pyo.NonNegativeReals)   # Downwards reserve limit for FD

# ----------------------------------------------------------
# 4. Wind Farm
# ----------------------------------------------------------

model.sgpw = pyo.Param(pyo.RangeSet(1, model.nT))   # stage associated to wind and PV production each hour
model.Pavg     = pyo.Param(within=pyo.Reals)    # Wind nominal power [MW]
model.pW = pyo.Param(model.T, model.S, within=pyo.NonNegativeReals, mutable=True)  # wind production
model.max_pW = pyo.Param(within=pyo.NonNegativeReals, mutable=True)                # maximum wind capacity

# ----------------------------------------------------------
# 5. Solar PV
# ----------------------------------------------------------

model.Pavg_PV  = pyo.Param(within=pyo.Reals)    # PV nominal power [MW]
model.pPV = pyo.Param(model.T, model.S, within=pyo.NonNegativeReals, mutable=True) 
model.max_pPV = pyo.Param(within=pyo.NonNegativeReals, mutable=True)

# ----------------------------------------------------------
# 6. Battery Energy Storage System
# ----------------------------------------------------------

model.Emax   = pyo.Param(within=pyo.NonNegativeReals)  # BESS capacity [MWh]
model.Dmax   = pyo.Param(within=pyo.NonNegativeReals)  # BESS max charge/discharge rate [MW]
model.RTE    = pyo.Param(within=pyo.NonNegativeReals)  # BESS round-trip efficiency
model.SOCmin = pyo.Param(within=pyo.NonNegativeReals)  # BESS minimum SOC
model.SOCmax = pyo.Param(within=pyo.NonNegativeReals)  # BESS maximum SOC
model.SOCini = pyo.Param(within=pyo.NonNegativeReals, mutable=True)  #  !!! BESS initial SOC It's mutable because every day has to be re-initialized
model.SOCfin = pyo.Param(within=pyo.NonNegativeReals)  # BESS final SOC
model.B_sp_cost = pyo.Param(within=pyo.NonNegativeReals)            # BESS specific replacement cost (€/MWh)
model.cyc_max = pyo.Param(within=pyo.NonNegativeReals)            # Total number of cycles in BESS lifetime (cycles)
# Computing BESS degradation cost
model.C_BESS = model.B_sp_cost/model.cyc_max              # cost per unit of battery degradation (€ / (MWh x cycle))

# =============================================================================
# 7. Hydrogen chain
# =============================================================================

# 7.1 Electrolyzer

# Set
model.Ndown_EL = pyo.Param(within=pyo.PositiveIntegers)     # minimum off-time periods [h]
# def NdownEL_init(m, t):
#     # build set of future periods for minimum down-time
#     start = t + 1
#     end   = min(t + pyo.value(m.Ndown_EL), pyo.value(m.nT))
#     return list(range(start, end+1)) if start <= end else []
# model.NEL_down = pyo.Set(model.T, initialize=NdownEL_init, ordered=True)

# Parameters
model.min_EL_frac = pyo.Param(within=pyo.NonNegativeReals)  # Minimum input power fraction when activated [0-1] 
model.P_EL_nom = pyo.Param(within=pyo.NonNegativeReals)     # Electrolyzer nominal power [MW] 
model.eta_EL = pyo.Param(within=pyo.NonNegativeReals)       # Electrolyzer efficiency [MWh/kg]
model.sp_wat_EL   = pyo.Param(within=pyo.NonNegativeReals)  # specific water consumption [L/kg H2]
model.lambda_wat   = pyo.Param(within=pyo.NonNegativeReals)  # water cost [€/L]
model.SB_frac      = pyo.Param(within=pyo.NonNegativeReals)  # standby fraction of power consumption [0-1]
model.EL_lifetime  = pyo.Param(within=pyo.PositiveReals)     # EL lifetime [hrs]
model.EL_repl_cost = pyo.Param(within=pyo.NonNegativeReals)  # Actualized replacement cost [€/MW]
model.lambda_warm_st  = pyo.Param(within=pyo.NonNegativeReals)    # warm startup cost [€/MW per event]
model.lambda_cold_st  = pyo.Param(within=pyo.NonNegativeReals)    # cold startup cost [€/MW per event]
model.iEL_on_ini   = pyo.Param(within=pyo.Binary, mutable=True) # Initial value for on state binary variable
model.iEL_sb_ini   = pyo.Param(within=pyo.Binary, mutable=True) # Initial value for standby state binary variable
model.iEL_off_ini  = pyo.Param(within=pyo.Binary, mutable=True) # Initial value for off state binary variable                                                                                                          

# 7.2 Compressor
model.spec_COMP = pyo.Param(within=pyo.NonNegativeReals)    # Compressor specific consumption [MWh/kg] 
model.P_COMP_nom = pyo.Param(within=pyo.NonNegativeReals)   # Compressor nominal power [MW]

# 7.3 Storage tank
model.H_tank_cap = pyo.Param(within=pyo.NonNegativeReals)               # Tank capacity [kg] 
model.LOH_ini = pyo.Param(within=pyo.NonNegativeReals, mutable=True)    # Initial level of hydrogen in tank [-] 
model.LOH_fin = pyo.Param(within=pyo.NonNegativeReals)                  # Final level of hydrogen in tank [-] 
model.P_tank = pyo.Param(within=pyo.NonNegativeReals)                   # Tank charge/discharge power [kg/h] 
model.eta_tank = pyo.Param(within=pyo.UnitInterval)                     # Tank round-trip efficiency [0-1] 
model.LOH_max = pyo.Param(within=pyo.NonNegativeReals)                  # Maximum LOH in tank [-] 
model.LOH_min = pyo.Param(within=pyo.NonNegativeReals)                  # Minimum LOH in tank [-]

# 7.4 Fuel cell
model.min_FC_frac = pyo.Param(within=pyo.NonNegativeReals)      # Minimum output power fraction when activated [0-1] 
model.P_FC_nom = pyo.Param(within=pyo.NonNegativeReals)         # Fuel cell nominal power [MW] 
model.eta_FC = pyo.Param(within=pyo.NonNegativeReals)           # Fuel cell efficiency [kg/MWh]
model.SB_frac_FC      = pyo.Param(within=pyo.NonNegativeReals)  # standby fraction of power consumption [0-1]
model.FC_lifetime  = pyo.Param(within=pyo.PositiveReals)     # FC lifetime [hrs]
model.FC_repl_cost = pyo.Param(within=pyo.NonNegativeReals)  # Actualized replacement cost [€/MW]
model.lambda_warm_st_FC  = pyo.Param(within=pyo.NonNegativeReals)    # warm startup cost [€/MW per event]
model.lambda_cold_st_FC  = pyo.Param(within=pyo.NonNegativeReals)    # cold startup cost [€/MW per event]
model.iFC_on_ini   = pyo.Param(within=pyo.Binary, mutable=True) # Initial value for on state binary variable
model.iFC_sb_ini   = pyo.Param(within=pyo.Binary, mutable=True) # Initial value for standby state binary variable
model.iFC_off_ini  = pyo.Param(within=pyo.Binary, mutable=True) # Initial value for off state binary variable                                                                                                          

# 7.5 Hydrogen demand
model.HDEM = pyo.Param(model.T, within=pyo.NonNegativeReals)    # Hydrogen demand at time t [kg]
model.HDEM_press = pyo.Param(within=pyo.NonNegativeReals)       # Hydrogen demand pressure [bar]
model.HEL_press	 = pyo.Param(within=pyo.NonNegativeReals)       # Electrolyzer operating pressure [bar]
model.lambda_H = pyo.Param(within=pyo.NonNegativeReals)         # Hydrogen price [€/kg]
model.can_sell_H2 = pyo.Param(within=pyo.Binary)                # Hydrogen can be sold or not? [0,1]                                                                                                                                                                                                             

# ----------------------------------------------------------
# 8. Market Participation
# ----------------------------------------------------------

# 8.1 Day Ahead Market 
model.lD = pyo.Param(model.T, model.S, within=pyo.Reals, mutable = True)    # !!! Day-ahead prices TO BE DEFINED BEFORE CREATING INSTANCE because they re used to create Ssd set

model.Ssd = pyo.Set(
    initialize=lambda m: [
        (t, l, j)
        for t in m.T
        for l in m.S
        for j in m.S
        if (pyo.value(m.lD[t, l]) <= pyo.value(m.lD[t, j]) and j != l)
    ]
)

model.PDA_LB = pyo.Param(within=pyo.NonNegativeReals)  # Minimum bid size [MWh]

# 8.2 Reserve Market
model.lR = pyo.Param(model.T, model.S, within=pyo.Reals, mutable=True)  # secondary reserve price
model.TSR = pyo.Param(within=pyo.NonNegativeReals)        # time response of SR

# 8.3 Intraday Market
model.lI = pyo.Param(model.IM, model.T, model.S, default=0.0, within=pyo.Reals, mutable=True)  
model.maxTIM = pyo.Param(within=pyo.Reals, default=0.2)

# 8.4 System Imbalances
model.lPIB = pyo.Param(model.T, model.S, within=pyo.NonNegativeReals, mutable=True)  # positive imbalance price
model.lNIB = pyo.Param(model.T, model.S, within=pyo.NonNegativeReals, mutable=True)  # negative imbalance price
model.PIB_p = pyo.Param(model.T, model.S, within=pyo.Reals, mutable=True)            # upper bound on positive imbalance
model.PIB_m = pyo.Param(model.T, model.S, within=pyo.Reals, mutable=True)            # upper bound on negative imbalance

# =============================================================================
# Parameters not used in the model but useful for Post-Processing in ec_run.py
# =============================================================================
# Below you'll see mutable = True, it means that values are filled after creating the instance (but before calling the solver). This can be done if none of these values are used to build sets in model.py.

# Wind Farm
model.mean_pW = pyo.Param(model.T, within=pyo.NonNegativeReals, mutable=True)      # average wind
model.sigma_pW = pyo.Param(model.T, within=pyo.NonNegativeReals, mutable=True, default=0.0)

# PV Farm
model.mean_pPV = pyo.Param(model.T, within=pyo.NonNegativeReals, mutable=True)     # average solar

# Day-Ahead market
model.mean_lD = pyo.Param(model.T, within=pyo.Reals, mutable=True)        # average day-ahead price

# Reserve market
model.mean_lR = pyo.Param(model.T, within=pyo.Reals, mutable=True)          # average reserve price

# Infraday market
model.mean_lI = pyo.Param(model.IM, model.T, within=pyo.Reals, mutable=True) # average IMs price

# Imbalances
model.lIB  = pyo.Param(model.T, model.S, within=pyo.Reals, mutable=True)             # imbalances price
model.mean_lPIB = pyo.Param(model.T, within=pyo.Reals, mutable=True)
model.mean_lNIB = pyo.Param(model.T, within=pyo.Reals, mutable=True)
model.mean_lIB  = pyo.Param(model.T, within=pyo.Reals, mutable=True)

# Parameters for the VSS Calculation
model.ScenF = pyo.Param(pyo.RangeSet(1, model.nRV), within=pyo.Reals)           # Forecasted scenario
model.ScenO = pyo.Param(pyo.RangeSet(1, model.nRV), within=pyo.Reals)           # Observed scenario
model.ScenE = pyo.Param(pyo.RangeSet(1, model.nRV), within=pyo.Reals, mutable=True, default=0.0) # Expected scenario

# Nearest Tree Scenario Parameters
model.min_dTO = pyo.Param(within=pyo.Reals, mutable=True, default=10**10)
model.sOR = pyo.Param(within=pyo.NonNegativeIntegers, mutable=True)

# Scenario Clustering and Probabilities
def SSG_init(model, sg):
    return sorted(set())  # Returns an empty set for each stage
model.SSG = pyo.Set(model.SG0, initialize=SSG_init, within=model.S0)

# Prob. of cluster c[sg,sc].
model.probc = pyo.Param(model.SG0, model.S, within=pyo.NonNegativeReals, mutable=True, default=0.0)

# # Intraday Market Bounds
# model.meanmax_pVI_RP = pyo.Param(model.IM, model.T, model.S, within=pyo.Reals, mutable=True, default=0.0)
# model.meanmin_pVI_RP = pyo.Param(model.IM, model.T, model.S, within=pyo.Reals, mutable=True, default=0.0)
# model.meanmax_pVI_EV = pyo.Param(model.IM, model.T, within=pyo.Reals, mutable=True, default=0.0)
# model.meanmin_pVI_EV = pyo.Param(model.IM, model.T, within=pyo.Reals, mutable=True, default=0.0)

# Define indexed sets for problem and simulations
model.PROB = pyo.Set(initialize=['ec'])  # This should be a fixed set of problems
model.SIMS = pyo.Set(initialize=[f"{i:03d}" for i in range(1, 366)])  # Extend as needed

# Elapsed Time Parameters
model.time = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.num_scen = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)

# Objective Function Components
model.obj_fun = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_DA_income = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_RM_income = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_IM_income = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_IB_income = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_H2_income = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_H2_DEM = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_IB_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_IB_net = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_FD_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_BESS_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_wat_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_warm_st_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_cold_st_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_deg_EL_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_warm_st_costs_FC = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_cold_st_costs_FC = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)
model.obj_deg_FC_costs = pyo.Param(model.PROB, model.SIMS, mutable=True, default=0.0)

# # Wind Uncertainty Parameters
# model.meanmax = pyo.Param(within=pyo.Reals, mutable=True, default=0.0)
# model.meanmin = pyo.Param(within=pyo.Reals, mutable=True, default=0.0)

# # Intraday Market Totals
# model.eIM_TOT = pyo.Param(model.T, model.S, within=pyo.Reals, mutable=True, default=0.0)


# =========================================================
# VARIABLES
# =========================================================

# 2. Flexible Demand
model.var_fd = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Flexible Demand [MW]
model.var_afd_p = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)   # Positive displacement
model.var_afd_m = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)   # Negative displacement

# 6. Battery Energy Storage System
model.dV = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)          # Discharge rate [MW]
model.cV = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)          # Charge rate [MW]
model.idV = pyo.Var(model.T, model.S, within=pyo.Binary)                   # Charge/discharge state (binary)
model.socV = pyo.Var(model.T0, model.S, within=pyo.NonNegativeReals, bounds = (model.SOCmin,model.SOCmax))

# 7.1 Electrolyzer 
model.eEL = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Electricity absorbed by the electrolyzer [MWh] 
model.eEL_on = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Electricity absorbed by the electrolyzer when producing hydrogen [MWh] 
model.eEL_sb = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Electricity absorbed by the electrolyzer when in stand-by [MWh] 
model.HEL = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Hydrogen produced by the electrolyzer [kg] 
# model.iEL = pyo.Var(model.T, model.S, within=pyo.Binary)               # Binary: electrolyzer active (1) or off (0)
model.HDIR_EL = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)  # Portion of HEL used directly to cover hydrogen demand (<0 only if demand P<30bar) [kg] 
model.HCOMP_EL = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals) # Portion of HEL to be sent to the compressor (100% of it if demand P>30bar) [kg]
model.iEL_on   = pyo.Var(model.T0, model.S, within=pyo.Binary)  # on-state
model.iEL_sb   = pyo.Var(model.T0, model.S, within=pyo.Binary)  # standby-state
model.iEL_off  = pyo.Var(model.T0, model.S, within=pyo.Binary)  # off-state
model.i_EL_warm = pyo.Var(model.T, model.S, within=pyo.Binary)  # warm start (sb->on)
model.i_EL_cold = pyo.Var(model.T, model.S, within=pyo.Binary)  # cold start (off->on)

# 7.2 Compressor 
model.eCOMP = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)        # Electricity absorbed by the compressor [MWh] 
# model.HCOMP = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Hydrogen output after compression [kg]
model.HDIR_COMP = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # Portion of compressed hydrogen used directly to cover hydrogen demand (>0 only if demand P>30bar) [kg] 
model.HC_TK = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)        # Portion of compressed hydrogen charged into the tank [kg]

# 7.3 Storage Tank
model.LOH = pyo.Var(model.T0, model.S, within=pyo.NonNegativeReals, bounds = (model.LOH_min, model.LOH_max)) # Level of hydrogen in the tank [-] 
model.HDISCH_TK = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)        # Hydrogen discharged from the tank [kg] 
model.HDIR_TK = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)          # Portion of discharged hydrogen used directly to meet demand [kg]
model.iTK = pyo.Var(model.T, model.S, within=pyo.Binary)                       # Binary: tank active (1) or not (0)

# 7.4 Fuel cell
model.HFC = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Hydrogen used by the fuel cell [kg]  
model.eFC_on = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # Electricity produced by the fuel cell in on state [MWh]
model.eFC_sb = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)      # Electricity produced by the fuel cell [MWh] 
# model.iFC = pyo.Var(model.T, model.S, within=pyo.Binary)               # Binary: fuel cell active (1) or off (0)
model.iFC_on   = pyo.Var(model.T0, model.S, within=pyo.Binary)  # on-state
model.iFC_sb   = pyo.Var(model.T0, model.S, within=pyo.Binary)  # standby-state
model.iFC_off  = pyo.Var(model.T0, model.S, within=pyo.Binary)  # off-state
model.i_FC_warm = pyo.Var(model.T, model.S, within=pyo.Binary)  # warm start (sb->on)
model.i_FC_cold = pyo.Var(model.T, model.S, within=pyo.Binary)  # cold start (off->on)

# Hydrogen sold
model.Hsold = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)  # Hydrogen sold [kg]               

# 8. Market Participation

# 8.1 Day Ahead Market
model.eDA_p = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)   # sold energy
model.eDA_m = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)   # bought energy
model.ieDA_p = pyo.Var(model.T, model.S, within=pyo.Binary)            # binary for selling bid
model.ieDA_m = pyo.Var(model.T, model.S, within=pyo.Binary)            # binary for buying bid

# 8.2 Reserve Market
model.rU = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)       # upward reserve
model.rD = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)       # downward reserve
model.rU_B = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)     # BESS upward reserve
model.rD_B = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)     # BESS downward reserve
model.rU_FD = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # FD upward reserve
model.rD_FD = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # FD downward reserve
# hydrogen chain components reserve market participation
model.rU_EL = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # EL Upward reserve [MW] 
model.rD_EL = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # EL Downward reserve [MW] 
model.rU_FC = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # FC Upward reserve [MW] 
model.rD_FC = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)    # FC Downward reserve [MW]

# 8.3 Intraday Markets
# "model.IM" is intraday markets, "model.TIM[i]" is the set of times for each market i
model.eIM = pyo.Var(model.IM, model.T, model.S)

# 8.4 System Imbalances
model.pIB_p = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)   # positive imbalance
model.pIB_m = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)   # negative imbalance

# Legacy Variables
# model.pPIB = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)
# model.pNIB = pyo.Var(model.T, model.S, within=pyo.NonNegativeReals)

# =========================================================
# OBJECTIVE FUNCTION
# =========================================================

def EECSW_rule(m):
    return sum(
        sum( m.Prob[s] * m.lD[t, s] * (m.eDA_p[t, s] - m.eDA_m[t, s]) for s in m.S ) +
        sum( m.Prob[s] * m.lR[t, s] * (m.rD[t, s] + m.rU[t, s]) for s in m.S ) +
        sum( m.Prob[s] * m.lI[i, t, s] * m.eIM[i, t, s] for s in m.S for i in m.IMT[t] ) +
        sum( m.Prob[s] * m.lPIB[t, s] * m.pIB_p[t, s] for s in m.S ) -
        sum( m.Prob[s] * m.lNIB[t, s] * m.pIB_m[t, s] for s in m.S ) -
        sum( m.Prob[s] * m.C_FD * (m.var_afd_p[t, s] + m.var_afd_m[t, s]) for s in m.S ) +
        m.lambda_H * m.HDEM[t] +
        sum( m.Prob[s] * m.lambda_H * m.Hsold[t, s] for s in m.S) -
        sum( m.Prob[s] * ((m.dV[t, s] + m.cV[t, s])/(2 * m.Emax)) * (m.B_sp_cost * m.Emax / m.cyc_max) for s in m.S) -
        sum( m.Prob[s] * m.lambda_wat * m.sp_wat_EL * m.HEL[t,s] for s in m.S ) -
        sum( m.Prob[s] * m.lambda_warm_st * m.P_EL_nom * m.i_EL_warm[t,s] for s in m.S ) -
        sum( m.Prob[s] * m.lambda_cold_st * m.P_EL_nom * m.i_EL_cold[t,s] for s in m.S ) -
        sum( m.Prob[s] * m.EL_repl_cost*m.P_EL_nom/m.EL_lifetime * m.iEL_on[t,s] for s in m.S ) -
        sum( m.Prob[s] * m.lambda_warm_st_FC * m.P_FC_nom * m.i_FC_warm[t,s] for s in m.S ) -
        sum( m.Prob[s] * m.lambda_cold_st_FC * m.P_FC_nom * m.i_FC_cold[t,s] for s in m.S ) -
        sum( m.Prob[s] * m.FC_repl_cost*m.P_FC_nom/m.FC_lifetime * m.iFC_on[t,s] for s in m.S )
        for t in m.T
    )
model.EECSW = pyo.Objective(rule=EECSW_rule, sense=pyo.maximize)

# =========================================================
# CONSTRAINTS
# =========================================================

# -------------------
# 2. Flexible Demand
# -------------------

# FD_L[t] <= var_fd[t, s] - TSR * rU_FD[t, s];
def FlexDem_LB_rule(m, t, s):
    return m.FD_L[t] <= m.var_fd[t, s] - m.TSR * m.rU_FD[t, s]
model.FlexDem_LB = pyo.Constraint(model.T, model.S, rule=FlexDem_LB_rule)

# var_fd[t, s] + TSR * rD_FD[t, s] <= FD_U[t];
def FlexDem_UB_rule(m, t, s):
    return m.var_fd[t, s] + m.TSR * m.rD_FD[t, s] <= m.FD_U[t]
model.FlexDem_UB = pyo.Constraint(model.T, model.S, rule=FlexDem_UB_rule)

# rD_FD[t, s] <= RDFD[t];
def FlexDemP_DReserve_rule(m, t, s):
    return m.rD_FD[t, s] <= m.RDFD[t]
model.FlexDemP_DReserve = pyo.Constraint(model.T, model.S, rule=FlexDemP_DReserve_rule)

# rU_FD[t, s] <= RUFD[t];
def FlexDemP_UReserve_rule(m, t, s):
    return m.rU_FD[t, s] <= m.RUFD[t]
model.FlexDemP_UReserve = pyo.Constraint(model.T, model.S, rule=FlexDemP_UReserve_rule)

# DailyDem: sum{t in T} var_fd[t, s] = sum{t in T} FD[t];
def DailyDem_rule(m, s):
    return sum(m.var_fd[t, s] for t in m.T) == sum(m.FD[t] for t in m.T)
model.DailyDem = pyo.Constraint(model.S, rule=DailyDem_rule)

# InterDem: sum_{t=TF_L[f]..TF_U[f]} var_fd[t, s] >= coef_FD[f]* sum_{t=TF_L[f]..TF_U[f]} FD[t];
def InterDem_rule(m, f, s):
    # gather time steps t in [TF_L[f], TF_U[f]]
    t_in_range = [t for t in m.T if m.TF_L[f] <= t <= m.TF_U[f]]
    return sum(m.var_fd[t, s] for t in t_in_range) >= m.coef_FD[f] * sum(m.FD[t] for t in t_in_range)
model.InterDem = pyo.Constraint(model.FI, model.S, rule=InterDem_rule)

# FD[t] - var_fd[t, s] = var_afd_p[t, s] - var_afd_m[t, s];
def FlexDemDisplace_rule(m, t, s):
    return m.FD[t] - m.var_fd[t, s] == m.var_afd_p[t, s] - m.var_afd_m[t, s]
model.FlexDemDisplace = pyo.Constraint(model.T, model.S, rule=FlexDemDisplace_rule)

# -------------------
# 5. Battery System
# -------------------

#### BESS opeartion
# dV[t,s] <= Dmax * idV[t,s];
def VPP_state_dV_rule(m, t, s):
    return m.dV[t, s] <= m.Dmax * m.idV[t, s]
model.VPP_state_dV = pyo.Constraint(model.T, model.S, rule=VPP_state_dV_rule)

# cV[t,s] <= Dmax * (1 - idV[t,s]);
def VPP_state_cV_rule(m, t, s):
    return m.cV[t, s] <= m.Dmax * (1 - m.idV[t, s])
model.VPP_state_cV = pyo.Constraint(model.T, model.S, rule=VPP_state_cV_rule)

# socV[t,s] = socV[t-1,s] + (cV[t,s] - dV[t,s]/RTE)/Emax;
def SOCV_rule(m, t, s):
    if t == m.T0.first():
        # skip t=0 because we define an initial condition separately
        return pyo.Constraint.Skip
    return m.socV[t, s] == m.socV[t-1, s] + (m.cV[t, s] - m.dV[t, s]/m.RTE)/m.Emax
model.SOCV = pyo.Constraint(model.T, model.S, rule=SOCV_rule)

# socV[first(T0), s] = SOCini;
def SOCV_ini_rule(m, s):
    # first(T0) is typically 0
    return m.socV[m.T0.first(), s] == m.SOCini
model.SOCV_ini = pyo.Constraint(model.S, rule=SOCV_ini_rule)

# socV[nT, s] = SOCfin;
def SOCV_fin_rule(m, s):
    return m.socV[m.nT, s] == m.SOCfin
model.SOCV_fin = pyo.Constraint(model.S, rule=SOCV_fin_rule)

#### BESS relation to reserve market
# rD_B[t,s] + cV[t,s] - dV[t,s] <= Dmax;
def VPP_RD2s_rule(m, t, s):
    return m.rD_B[t, s] + m.cV[t, s] - m.dV[t, s] <= m.Dmax
model.VPP_RD2s = pyo.Constraint(model.T, model.S, rule=VPP_RD2s_rule)

# rU_B[t,s] - cV[t,s] + dV[t,s] <= Dmax;
def VPP_RU2s_rule(m, t, s):
    return m.rU_B[t, s] - m.cV[t, s] + m.dV[t, s] <= m.Dmax
model.VPP_RU2s = pyo.Constraint(model.T, model.S, rule=VPP_RU2s_rule)

# SOCmin <= socV[t,s] - TSR*rU_B[t,s]/(RTE*Emax);
def VPP_RU_SOCV_rule(m, t, s):
    return m.SOCmin <= m.socV[t, s] - m.TSR * m.rU_B[t, s] / (m.RTE * m.Emax)
model.VPP_RU_SOCV = pyo.Constraint(model.T, model.S, rule=VPP_RU_SOCV_rule)

# socV[t,s] + TSR*rD_B[t,s]/Emax <= SOCmax;
def VPP_RD_SOCV_rule(m, t, s):
    return m.socV[t, s] + m.TSR*m.rD_B[t, s]/m.Emax <= m.SOCmax
model.VPP_RD_SOCV = pyo.Constraint(model.T, model.S, rule=VPP_RD_SOCV_rule)

# =============================================================================
# Hydrogen chain
# =============================================================================

# =============================================================================
# 7.1 Electrolyzer
# =============================================================================

### THESE TWO CONTRAINTS ARE INCLUDED IN THE RESERVE ELECTROLYZER CONSTRAINTS, SO ARE COMMENTED

def EL_min_power_rule(m, t, s):
    # When active, the electrolyzer must consume at least the minimum fraction of its nominal power.
    return m.eEL_on[t, s] >= m.min_EL_frac * m.P_EL_nom * m.iEL_on[t, s]
model.EL_min_power = pyo.Constraint(model.T, model.S, rule=EL_min_power_rule)

def EL_max_power_rule(m, t, s):
    # The electrolyzer consumption cannot exceed its nominal power.
    return m.eEL_on[t, s] <= m.P_EL_nom * m.iEL_on[t, s]
model.EL_max_power = pyo.Constraint(model.T, model.S, rule=EL_max_power_rule)

def EL_hydrogen_production_rule(m, t, s):
    return m.eEL_on[t,s] == m.eta_EL * m.HEL[t,s] 
model.EL_hydrogen_prod = pyo.Constraint(model.T, model.S, rule=EL_hydrogen_production_rule)

# The hydrogen output after electrolysis is split into the portion used directly to cover demand and that to be compressed.
def EL_split_rule(m, t, s):
    return m.HEL[t,s] == m.HDIR_EL[t,s] + m.HCOMP_EL[t,s]
model.EL_split = pyo.Constraint(model.T, model.S, rule=EL_split_rule)

# Electricity consumed in stand-by conditions
def EL_SB_balance_rule(m, t, s):
    return m.eEL_sb[t,s] == m.SB_frac * m.P_EL_nom * m.iEL_sb[t, s]
model.EL_SB_energy_balance = pyo.Constraint(model.T, model.S, rule=EL_SB_balance_rule)

# Total electricity absorbed by electrolyzer
def EL_energy_balance_rule(m, t, s):
    return m.eEL[t,s] == m.eEL_on[t,s] + m.eEL_sb[t,s]
model.EL_energy_balance = pyo.Constraint(model.T, model.S, rule=EL_energy_balance_rule)

# --- MODE TRANSITION CONSTRAINTS ---
# sanity‐check for the initial state that they sum to one:
model.EL_ini_sum = pyo.Constraint(expr=model.iEL_on_ini + model.iEL_sb_ini + model.iEL_off_ini == 1)                                                                                              

model.EL_on_ini  = pyo.Constraint(model.S, rule=lambda m,s: m.iEL_on[0,s]  == m.iEL_on_ini)
model.EL_sb_ini  = pyo.Constraint(model.S, rule=lambda m,s: m.iEL_sb[0,s]  == m.iEL_sb_ini)
model.EL_off_ini = pyo.Constraint(model.S, rule=lambda m,s: m.iEL_off[0,s] == m.iEL_off_ini)

# Only one state per time
def EL_one_state_rule(m, t, s):
    return m.iEL_on[t,s] + m.iEL_sb[t,s] + m.iEL_off[t,s] == 1
model.EL_one_state = pyo.Constraint(model.T, model.S, rule=EL_one_state_rule)

# # Downtime constraint
# def EL_downtime_rule(m, t, s, n):
#     # if turned off at t, must remain off for all n in NEL_down[t]
#     if t == m.T.first():
#         return pyo.Constraint.Skip
#     return m.iEL_off[t,s] - m.iEL_off[t-1,s] <= m.iEL_off[n,s]
# model.EL_downtime = pyo.Constraint(model.T, model.S, model.NEL_down, rule=EL_downtime_rule)

# no transition sb->off or off->sb
def EL_no_sb_off_rule(m, t, s):
    return m.iEL_off[t,s] <= 1 - m.iEL_sb[t-1,s]
model.EL_no_sb_off1 = pyo.Constraint(model.T, model.S, rule=EL_no_sb_off_rule)

def EL_no_off_sb_rule(m, t, s):                         
    return  m.iEL_sb[t,s] <= 1 - m.iEL_off[t-1,s]
model.EL_no_sb_off2 = pyo.Constraint(model.T, model.S, rule=EL_no_off_sb_rule)

# Warm/cold startup linking (linearized)
def EL_warm_start_lower(m, t, s):                                 
    return m.iEL_sb[t-1, s] + m.iEL_on[t, s] - 1 <= m.i_EL_warm[t, s]
model.EL_warm_lower = pyo.Constraint(model.T, model.S, rule=EL_warm_start_lower)

# def EL_warm_start_upper1(m, t, s):                          
#     return m.i_EL_warm[t,s] <= m.iEL_sb[t-1, s]
# model.EL_warm_upper1 = pyo.Constraint(model.T, model.S, rule=EL_warm_start_upper1)

# def EL_warm_start_upper2(m, t, s):                            
#     return m.i_EL_warm[t,s] <= m.iEL_on[t,s]
# model.EL_warm_upper2 = pyo.Constraint(model.T, model.S, rule=EL_warm_start_upper2)

# Cold start (off->on)
def EL_cold_start_lower(m, t, s):                                     
    return m.iEL_off[t-1, s] + m.iEL_on[t,s] - 1 <= m.i_EL_cold[t,s]
model.EL_cold_lower = pyo.Constraint(model.T, model.S, rule=EL_cold_start_lower)

# def EL_cold_start_upper1(m, t, s):                      
#     return m.i_EL_cold[t,s] <= m.iEL_off[t-1, s]
# model.EL_cold_upper1 = pyo.Constraint(model.T, model.S, rule=EL_cold_start_upper1)

# def EL_cold_start_upper2(m, t, s):
#     return m.i_EL_cold[t,s] <= m.iEL_on[t,s]
# model.EL_cold_upper2 = pyo.Constraint(model.T, model.S, rule=EL_cold_start_upper2)

# Reserve market constraints for the electrolyzer
def EL_RU_rule(m, t, s):
    # the effective consumption (baseline minus reserve) must remain above the minimum. 
    # It can provide upward reserve only in on mode, because in standby the consumption is minimal
    return m.eEL_on[t,s] - m.rU_EL[t,s] >= m.min_EL_frac * m.P_EL_nom * m.iEL_on[t,s]
model.EL_upward_reserve = pyo.Constraint(model.T, model.S, rule=EL_RU_rule)

def EL_RD_rule(m, t, s):
    # the effective consumption (baseline plus reserve) must not exceed nominal power.
    # The eelctrolyzer can provide downward reserve not only in on mode but even in standby mode
    return m.eEL[t,s] + m.rD_EL[t,s] <= m.P_EL_nom * (1 - m.iEL_off[t,s])
model.EL_downward_reserve = pyo.Constraint(model.T, model.S, rule=EL_RD_rule)

def EL_RD_LOH_rule(m, t, s):
    # Tank capacity limit to be respected when providing downward reserve only if hydrogen can't be sold
    if m.can_sell_H2 == 0:
        return m.LOH[t, s] + m.TSR * m.rD_EL[t, s] / (m.eta_EL * m.H_tank_cap) <= m.LOH_max
    else:
        return pyo.Constraint.Skip
model.HEL_RD_LOH = pyo.Constraint(model.T, model.S, rule=EL_RD_LOH_rule)

def EL_RU_LOH_rule(m, t, s):
    # Tank capacity limit to be respected when providing upward reserve
    return m.LOH[t, s] - m.TSR * m.rU_EL[t, s] / (m.eta_EL * m.H_tank_cap) >= m.LOH_min
model.HEL_RU_LOH = pyo.Constraint(model.T, model.S, rule=EL_RU_LOH_rule)

# =============================================================================
# 7.2 Compressor
# =============================================================================

def COMP_energy_rule(m, t, s):
    return m.eCOMP[t,s] == m.spec_COMP * m.HCOMP_EL[t,s]
model.COMP_energy = pyo.Constraint(model.T, model.S, rule=COMP_energy_rule)

def COMP_power_rule(m, t, s):
    return m.eCOMP[t,s] <= m.P_COMP_nom
model.COMP_power = pyo.Constraint(model.T, model.S, rule=COMP_power_rule)

# The hydrogen output after compression is split into the portion used directly to cover demand and that charged into the tank.
def COMP_split_rule(m, t, s):
    return m.HCOMP_EL[t,s] == m.HDIR_COMP[t,s] + m.HC_TK[t,s]
model.COMP_split = pyo.Constraint(model.T, model.S, rule=COMP_split_rule)

# =============================================================================
# 7.3 Storage Tank
# =============================================================================

def Tank_initial_rule(m, s):
    return m.LOH[m.T0.first(), s] == m.LOH_ini
model.Tank_initial = pyo.Constraint(model.S, rule=Tank_initial_rule)

def Tank_final_rule(m, s):
    return m.LOH[m.nT, s] == m.LOH_fin
model.Tank_final = pyo.Constraint(model.S, rule=Tank_final_rule)

def Tank_charge_rate_rule(m, t, s):
    # If the tank is charging (iTK = 0) then the charging flow (HC_TK) must be no more than the maximum.
    return m.HC_TK[t,s] <= m.P_tank * (1 - m.iTK[t,s])
model.Tank_charge_rate = pyo.Constraint(model.T, model.S, rule=Tank_charge_rate_rule)

def Tank_discharge_rate_rule(m, t, s):
    # If the tank is discharging (iTK = 1) then the discharging flow (HDISCH_TK) is limited.
    return m.HDISCH_TK[t,s] <= m.P_tank * m.iTK[t,s]
model.Tank_discharge_rate = pyo.Constraint(model.T, model.S, rule=Tank_discharge_rate_rule)

# The hydrogen discharged from the tank is split into the portion used to cover demand and that used to fuel the fuel cell.
def Tank_split_rule(m, t, s):
    return m.HDISCH_TK[t,s] == m.HDIR_TK[t,s] + m.HFC[t,s]
model.Tank_split = pyo.Constraint(model.T, model.S, rule=Tank_split_rule)

def Tank_storage_rule(m, t, s):
    if t == m.T0.first():
        return pyo.Constraint.Skip
    return m.LOH[t,s] == m.LOH[t-1,s] + (m.HC_TK[t,s] - m.HDISCH_TK[t,s] / m.eta_tank) / m.H_tank_cap
model.Tank_storage = pyo.Constraint(model.T, model.S, rule=Tank_storage_rule)

# =============================================================================
# 7.4 Fuel Cell
# =============================================================================

### THESE TWO CONTRAINTS ARE INCLUDED IN THE RESERVE FUEL CELL CONSTRAINTS, SO ARE COMMENTED

def FC_min_power_rule(m, t, s):
    # When active, the fuel cell must produce at least the minimum fraction of its nominal power.
    return m.eFC_on[t, s] >= m.min_FC_frac * m.P_FC_nom * m.iFC_on[t, s]
model.FC_min_power = pyo.Constraint(model.T, model.S, rule=FC_min_power_rule)

def FC_max_power_rule(m, t, s):
    # The fuel cell production cannot exceed its nominal power.
    return m.eFC_on[t, s] <= m.P_FC_nom * m.iFC_on[t, s]
model.FC_max_power = pyo.Constraint(model.T, model.S, rule=FC_max_power_rule)

def FC_hydrogen_cons_rule(m, t, s):
    return m.HFC[t,s] == m.eFC_on[t, s] * m.eta_FC
model.FC_hydrogen_cons = pyo.Constraint(model.T, model.S, rule=FC_hydrogen_cons_rule)

# Electricity consumed in stand-by conditions by the FC (not hydrogen but electricity when in standby)
def FC_SB_balance_rule(m, t, s):
    return m.eFC_sb[t,s] == m.SB_frac_FC * m.P_FC_nom * m.iFC_sb[t, s]
model.FC_SB_energy_balance = pyo.Constraint(model.T, model.S, rule=FC_SB_balance_rule)

# --- MODE TRANSITION CONSTRAINTS ---
# sanity‐check for the initial state that they sum to one:
model.FC_ini_sum = pyo.Constraint(expr=model.iFC_on_ini + model.iFC_sb_ini + model.iFC_off_ini == 1)                                                                                              

model.FC_on_ini  = pyo.Constraint(model.S, rule=lambda m,s: m.iFC_on[0,s]  == m.iFC_on_ini)
model.FC_sb_ini  = pyo.Constraint(model.S, rule=lambda m,s: m.iFC_sb[0,s]  == m.iFC_sb_ini)
model.FC_off_ini = pyo.Constraint(model.S, rule=lambda m,s: m.iFC_off[0,s] == m.iFC_off_ini)

# Only one state per time
def FC_one_state_rule(m, t, s):
    return m.iFC_on[t,s] + m.iFC_sb[t,s] + m.iFC_off[t,s] == 1
model.FC_one_state = pyo.Constraint(model.T, model.S, rule=FC_one_state_rule)

# no transition sb->off or off->sb
def FC_no_sb_off_rule(m, t, s):
    return m.iFC_off[t,s] <= 1 - m.iFC_sb[t-1,s]
model.FC_no_sb_off1 = pyo.Constraint(model.T, model.S, rule=FC_no_sb_off_rule)

def FC_no_off_sb_rule(m, t, s):
    return  m.iFC_sb[t,s] <= 1 - m.iFC_off[t-1,s]
model.FC_no_sb_off2 = pyo.Constraint(model.T, model.S, rule=FC_no_off_sb_rule)

# Warm/cold startup linking (linearized)
def FC_warm_start_lower(m, t, s):
    return m.iFC_sb[t-1, s] + m.iFC_on[t,s] - 1 <= m.i_FC_warm[t,s]
model.FC_warm_lower = pyo.Constraint(model.T, model.S, rule=FC_warm_start_lower)

# def FC_warm_start_upper1(m, t, s):    
#     return m.i_FC_warm[t,s] <= m.iFC_sb[t-1, s]
# model.FC_warm_upper1 = pyo.Constraint(model.T, model.S, rule=FC_warm_start_upper1)

# def FC_warm_start_upper2(m, t, s):
#     return m.i_FC_warm[t,s] <= m.iFC_on[t,s]
# model.FC_warm_upper2 = pyo.Constraint(model.T, model.S, rule=FC_warm_start_upper2)

# Cold start (off->on)
def FC_cold_start_lower(m, t, s):
    return m.iFC_off[t-1, s] + m.iFC_on[t,s] - 1 <= m.i_FC_cold[t,s]
model.FC_cold_lower = pyo.Constraint(model.T, model.S, rule=FC_cold_start_lower)

# def FC_cold_start_upper1(m, t, s): 
#     return m.i_FC_cold[t,s] <= m.iFC_off[t-1, s]
# model.FC_cold_upper1 = pyo.Constraint(model.T, model.S, rule=FC_cold_start_upper1)

# def FC_cold_start_upper2(m, t, s):
#     return m.i_FC_cold[t,s] <= m.iFC_on[t,s]
# model.FC_cold_upper2 = pyo.Constraint(model.T, model.S, rule=FC_cold_start_upper2)

def FC_RU_rule(m, t, s):
    # When providing upward reserve, the effective production (production plus reserve) must not exceed nominal power.
    # The fuel cell can provide upward reserve not only in on mode but even in standby mode
    return m.eFC_on[t,s] - m.eFC_sb[t,s] +  m.rU_FC[t,s] <= m.P_FC_nom * (1 - m.iFC_off[t,s])
model.FC_reserve_upward = pyo.Constraint(model.T, model.S, rule=FC_RU_rule)

def FC_RD_rule(m, t, s):
    # When providing downward reserve, the effective production (production minus reserve) must remain above the minimum.
    # It can provide downward reserve only in on mode, because in standby the consumption is minimal
    return m.eFC_on[t,s] - m.rD_FC[t,s] >= m.min_FC_frac * m.P_FC_nom * m.iFC_on[t,s]
model.FC_reserve_downward = pyo.Constraint(model.T, model.S, rule=FC_RD_rule)

def FC_RU_LOH_rule(m, t, s):
    # Minimum Tank capacity must always be guaranteed when providing upward reserve
    return m.LOH[t, s] - m.TSR * m.rU_FC[t, s] * m.eta_FC / (m.eta_tank * m.H_tank_cap) >= m.LOH_min
model.HFC_RU_LOH = pyo.Constraint(model.T, model.S, rule=FC_RU_LOH_rule)

def FC_RD_LOH_rule(m, t, s):
    # Minimum Tank capacity must always be guaranteed when providing upward reserve
    return m.LOH[t, s] + m.TSR * m.rD_FC[t, s] * m.eta_FC / (m.eta_tank * m.H_tank_cap) <= m.LOH_max
model.HFC_RD_LOH = pyo.Constraint(model.T, model.S, rule=FC_RD_LOH_rule)

# =============================================================================
# 7.5 Hydrogen demand
# =============================================================================

# The hydrogen demand can be covered directly after electrolysis (if P<30 bar), directly after compression (if P > 30 bar), or from the tank after being laminated if P < 30 bar
# Hypotesis: if Demand P>30 bar, Compressor output pressure = Tank Pressure = Demand pressure
def DEM_split_rule(m, t, s):
    return  m.HDIR_COMP[t,s] + m.HDIR_EL[t,s] + m.HDIR_TK[t,s] >= m.HDEM[t]
model.DEM_split = pyo.Constraint(model.T, model.S, rule=DEM_split_rule)

# If hydrogen demand pressure is lower than 30 bar then no direct supply from compressor is allowed,
# while if it is higher than 30 bar, no direct supply from electrolyzer is allowed
def H2_direct_use_rule(m, t, s): 
    if m.HDEM_press <= m.HEL_press:
        return m.HDIR_COMP[t,s] == 0
    else:
        return m.HDIR_EL[t,s] == 0
model.H2_direct_use = pyo.Constraint(model.T, model.S, rule=H2_direct_use_rule)

# define Hsold = total hydrogen allocated – demand
def Hsold_balance_rule(m, t, s):
    return m.Hsold[t, s] == m.HDIR_COMP[t, s] + m.HDIR_EL[t, s] + m.HDIR_TK[t, s] - m.HDEM[t]
model.Hsold_balance = pyo.Constraint(model.T, model.S, rule=Hsold_balance_rule)

# only when can_sell_H2==0 do we force Hsold == 0,
# otherwise we skip this constraint and let other bounds apply
def Hsold_zero_if_no_sell(m, t, s):
    if m.can_sell_H2 == 0:
        return m.Hsold[t, s] == 0
    else:
        return pyo.Constraint.Skip
model.Hsold_zero_if_no_sell = pyo.Constraint(model.T, model.S, rule=Hsold_zero_if_no_sell)

# -------------------------------------------------------
# 8.1 Day Ahead Market
# -------------------------------------------------------

# Lower & Upper Bounds on DA Sell & Buy Energy
def DA_sell_bid_LB_rule(m, t, s):
    return m.PDA_LB * m.ieDA_p[t, s] <= m.eDA_p[t, s]
model.DA_sell_bid_LB = pyo.Constraint(model.T, model.S, rule=DA_sell_bid_LB_rule)

def DA_sell_bid_UB_rule(m, t, s):
    # return m.eDA_p[t, s] <= (m.max_pW + m.max_pPV + m.Dmax - m.FD_L[t]) * m.ieDA_p[t, s]
    # Modified to take into account even the hydrogen chain! 
    return m.eDA_p[t, s] <= (m.max_pW + m.max_pPV + m.Dmax + m.P_FC_nom - m.FD_L[t]) * m.ieDA_p[t, s]
model.DA_sell_bid_UB = pyo.Constraint(model.T, model.S, rule=DA_sell_bid_UB_rule)

def DA_buy_bid_LB_rule(m, t, s):
    return m.PDA_LB * m.ieDA_m[t, s] <= m.eDA_m[t, s]
model.DA_buy_bid_LB = pyo.Constraint(model.T, model.S, rule=DA_buy_bid_LB_rule)

def DA_buy_bid_UB_rule(m, t, s):
    # return m.eDA_m[t, s] <= (m.Dmax + m.FD_U[t]) * m.ieDA_m[t, s]
    # Modified to take into account even the hydrogen chain!
    return m.eDA_m[t, s] <= (m.Dmax + m.FD_U[t] + m.P_EL_nom + m.P_COMP_nom + m.SB_frac_FC*m.P_FC_nom) * m.ieDA_m[t, s]
model.DA_buy_bid_UB = pyo.Constraint(model.T, model.S, rule=DA_buy_bid_UB_rule)

# Constraint to Ensure Either Buying or Selling, Not Both
def DA_buy_or_sell_rule(m, t, s):
    return m.ieDA_m[t, s] + m.ieDA_p[t, s] <= 1
model.DA_buy_or_sell = pyo.Constraint(model.T, model.S, rule=DA_buy_or_sell_rule)

# DA monotonicity constraints (eDA_p[t,l] <= eDA_p[t,k], eDA_m[t,l] >= eDA_m[t,k])
def DA_bid_mono_1_rule(m, t, l, k):
    return m.eDA_p[t, l] <= m.eDA_p[t, k]
model.DA_bid_mono_1 = pyo.Constraint(model.Ssd, rule=DA_bid_mono_1_rule)

def DA_bid_mono_2_rule(m, t, l, k):
    return m.eDA_m[t, l] >= m.eDA_m[t, k]
model.DA_bid_mono_2 = pyo.Constraint(model.Ssd, rule=DA_bid_mono_2_rule)

# -------------------------------------------------------
# 8.2 Reserve Market
# -------------------------------------------------------

# rU[t,s] = rU_B[t,s] + rU_FD[t,s];
def RM_components_U_rule(m, t, s):
    # return m.rU[t, s] == m.rU_B[t, s] + m.rU_FD[t, s]
    # Modified to take into account even the hydrogen chain!
    return m.rU[t, s] == m.rU_B[t, s] + m.rU_FD[t, s] + m.rU_EL[t, s] + m.rU_FC[t, s]
model.RM_components_U = pyo.Constraint(model.T, model.S, rule=RM_components_U_rule)

# rD[t,s] = rD_B[t,s] + rD_FD[t,s];
def RM_components_D_rule(m, t, s):
    # return m.rD[t, s] == m.rD_B[t, s] + m.rD_FD[t, s]
    # Modified to take into account even the hydrogen chain!
    return m.rD[t, s] == m.rD_B[t, s] + m.rD_FD[t, s] + m.rD_EL[t, s] + m.rD_FC[t, s]
model.RM_components_D = pyo.Constraint(model.T, model.S, rule=RM_components_D_rule)

# (Optional) Monotonicity constraints for Reserve Market are commented out in ec.mod
# If you decide to activate them, replicate similarly to DA monotonicity.

# -------------------------------------------------------
# 8.3 Intraday Markets
# -------------------------------------------------------

# - maxTIM*(eDA_p[t,s]+eDA_m[t,s]) <= sum{i in IMT[t]} eIM[i,t,s];
def IM_bounds_1_rule(m, t, s):
    return -m.maxTIM * (m.eDA_p[t, s] + m.eDA_m[t, s]) <= sum(m.eIM[i, t, s] for i in m.IMT[t])
model.IM_bounds_1 = pyo.Constraint(model.T, model.S, rule=IM_bounds_1_rule)

# sum{i in IMT[t]} eIM[i,t,s] <= maxTIM*(eDA_p[t,s]+eDA_m[t,s]);
def IM_bounds_2_rule(m, t, s):
    return sum(m.eIM[i, t, s] for i in m.IMT[t]) <= m.maxTIM * (m.eDA_p[t, s] + m.eDA_m[t, s])
model.IM_bounds_2 = pyo.Constraint(model.T, model.S, rule=IM_bounds_2_rule)

# - maxTIM*(eDA_p[t,s]+eDA_m[t,s]) <= eIM[i,t,s];
def IM_bounds_3_rule(m, i, t, s):
    return -m.maxTIM * (m.eDA_p[t, s] + m.eDA_m[t, s]) <= m.eIM[i, t, s]
model.IM_bounds_3 = pyo.Constraint(model.IM, model.T, model.S, rule=IM_bounds_3_rule)

# eIM[i,t,s] <= maxTIM*(eDA_p[t,s]+eDA_m[t,s]);
def IM_bounds_4_rule(m, i, t, s):
    return m.eIM[i, t, s] <= m.maxTIM * (m.eDA_p[t, s] + m.eDA_m[t, s])
model.IM_bounds_4 = pyo.Constraint(model.IM, model.T, model.S, rule=IM_bounds_4_rule)

# (Optional) lI_bid monotonicity constraints for IM are commented out in ec.mod

# -------------------------------------------------------
# 8.4 System Imbalances
# -------------------------------------------------------

def Imbalances_rule(m, t, s):
    lhs = m.pIB_p[t, s] - m.pIB_m[t, s]
    # rhs = (m.eDA_m[t, s] + m.pW[t, s] + m.pPV[t, s] + m.dV[t, s]
    #        - m.eDA_p[t, s] - sum(m.eIM[i, t, s] for i in m.IMT[t]) - m.var_fd[t, s] - m.cV[t, s])
    # Modified to take into account even the hydrogen chain!
    rhs = (m.eDA_m[t, s] + m.pW[t, s] + m.pPV[t, s] + m.dV[t, s] + m.eFC_on[t,s]
           - m.eDA_p[t, s] - sum(m.eIM[i, t, s] for i in m.IMT[t]) - m.var_fd[t, s] - m.cV[t, s] - m.eEL[t,s] - m.eCOMP[t,s] - m.eFC_sb[t,s])
    return lhs == rhs
model.Imbalances = pyo.Constraint(model.T, model.S, rule=Imbalances_rule)

# pIB_p[t,s] <= PIB_p[t,s];
def IB_pos_UB_rule(m, t, s):
    return m.pIB_p[t, s] <= m.PIB_p[t, s]
model.IB_pos_UB = pyo.Constraint(model.T, model.S, rule=IB_pos_UB_rule)

# pIB_m[t,s] <= PIB_m[t,s];
def IB_neg_UB_rule(m, t, s):
    return m.pIB_m[t, s] <= m.PIB_m[t, s]
model.IB_neg_UB = pyo.Constraint(model.T, model.S, rule=IB_neg_UB_rule)


# =============================================================================
# Nonanticipativity Constraints
# =============================================================================

"""
Defines all the nonanticipativity constraints from the ec.mod file,
implementing the 'next(l, c[sg,k],1)' logic in Pyomo for an AbstractModel.
"""

# ---------------------------------------------------------
# HELPER FUNCTION to replicate AMPL's "next(l, c[sg,k],1)"
# ---------------------------------------------------------

def consecutive_scenarios(model, sg, k):
    if (sg, k) not in model.c.index_set():
        return []
    # Sort using the same numeric key!
    scenario_list = sorted([l for l in model.c[sg, k] if l in model.S],
                           key=lambda x: int(x))
    return [(scenario_list[i], scenario_list[i+1]) for i in range(len(scenario_list)-1)]

# ---------------------------------------------------------------------
# 1) DAY-AHEAD + RESERVE (stage=1) (c[1, k])
#    Variables: eDA_p, eDA_m, ieDA_p, ieDA_m, rU, rU_B, rU_FD, rD, rD_B, rD_FD
# ---------------------------------------------------------------------
def build_stage1_nac_index(model):
    """
    Builds a single index set for all day-ahead & reserve variables that share
    the same stage=1 logic and indexing (t, s).
    We'll store tuples: (var_name, t, k, l, l_next).
    """
    day_ahead_reserve_vars = [
        "eDA_p", "eDA_m", "ieDA_p", "ieDA_m",
        "rU", "rU_B", "rU_FD", "rU_EL", "rU_FC",
        "rD", "rD_B", "rD_FD", "rD_EL", "rD_FC"
    ]
    idx = []
    for var_name in day_ahead_reserve_vars:
        var_obj = getattr(model, var_name)
        for t in model.T:
            for k in model.S0:
                # stage=1 for these
                for (l, l_next) in consecutive_scenarios(model, 1, k):
                    # skip if not in domain
                    if (t, l) in var_obj and (t, l_next) in var_obj:
                        idx.append((var_name, t, k, l, l_next))
    return idx

def stage1_nac_rule(m, var_name, t, k, l, l_next):
    var_obj = getattr(m, var_name)
    return var_obj[t, l] == var_obj[t, l_next]

model.NAC_stage1_index = pyo.Set(dimen=5, initialize=build_stage1_nac_index)
model.NAC_stage1 = pyo.Constraint(model.NAC_stage1_index, rule=stage1_nac_rule)

# ---------------------------------------------------------
# INTRADAY MARKETS: eIM referencing c[sgim[i]-1, k]
# ---------------------------------------------------------
def build_nac_eIM_index(model):
    idx = []
    for i in model.IM:
        for t in model.TIM[i]:
            for k in model.S0:
                sg_for_i = model.sgim[i] - 1
                if (sg_for_i, k) in model.c.index_set():  # Ensure (sg, k) exists
                    for (l, l_next) in consecutive_scenarios(model, sg_for_i, k):
                        if l in model.S and l_next in model.S:  # Ensure valid indices
                            idx.append((i, t, k, l, l_next))
    return idx

def NAC_eIM_rule(m, i, t, k, l, l_next):
    if (i, t, l) not in m.eIM or (i, t, l_next) not in m.eIM:
        return pyo.Constraint.Skip
    return m.eIM[i, t, l] == m.eIM[i, t, l_next]

model.NAC_eIM_index = pyo.Set(dimen=5, initialize=build_nac_eIM_index)
model.NAC_eIM = pyo.Constraint(model.NAC_eIM_index, rule=NAC_eIM_rule)

# ---------------------------------------------------------------------
# 3) IMBALANCES: pIB_p, pIB_m referencing c[ sgpw[t], k ]
# ---------------------------------------------------------------------
def build_nac_imbal_index(model):
    """
    We'll unify pIB_p and pIB_m in one NAC set.
    We'll store (var_name, t, k, l, l_next).
    """
    imbal_vars = ["pIB_p", "pIB_m"]
    idx = []
    for var_name in imbal_vars:
        var_obj = getattr(model, var_name)
        for t in model.T:
            sg_for_t = model.sgpw[t]
            for k in model.S0:
                if (sg_for_t, k) in model.c.index_set():
                    for (l, l_next) in consecutive_scenarios(model, sg_for_t, k):
                        if (t, l) in var_obj and (t, l_next) in var_obj:
                            idx.append((var_name, t, k, l, l_next))
    return idx

def nac_imbal_rule(m, var_name, t, k, l, l_next):
    var_obj = getattr(m, var_name)
    return var_obj[t, l] == var_obj[t, l_next]

model.NAC_imbal_index = pyo.Set(dimen=5, initialize=build_nac_imbal_index)
model.NAC_imbal = pyo.Constraint(model.NAC_imbal_index, rule=nac_imbal_rule)

# ---------------------------------------------------------------------
# 4) FLEXIBLE DEMAND + BATTERY + ELECTROLYZER + COMPRESSOR + TANK + FUEL CELL (stage = sgpw[t]-1)
#    Variables: var_fd, var_afd_p, var_afd_m, dV, cV, idV, socV
# ---------------------------------------------------------------------


def build_nac_fd_battery_index(model):
    """
    We'll unify FLEXIBLE DEMAND + BATTERY + ELECTROLYZER + COMPRESSOR + TANK + FUEL CELL in one NAC set, referencing c[sgpw[t]-1, k].
    We'll store (var_name, t, k, l, l_next).
    """
    fd_batt_vars = [
        "var_fd", "var_afd_p", "var_afd_m",
        "dV", "cV", "idV", "socV",
        "eEL", "eEL_on", "eEL_sb", "iEL_on", "iEL_sb", "iEL_off", "i_EL_warm", "i_EL_cold", "HEL", "HDIR_EL", "HCOMP_EL",
        "eCOMP", "HDIR_COMP", "HC_TK",
        "LOH", "HDISCH_TK", "HDIR_TK", "iTK",
        "HFC", "eFC_on", "eFC_sb", "iFC_on", "iFC_sb", "iFC_off", "i_FC_warm", "i_FC_cold",
        "Hsold"                     
    ]
    idx = []
    for var_name in fd_batt_vars:
        var_obj = getattr(model, var_name)
        for t in model.T:
            sg_for_t_minus1 = model.sgpw[t] - 1
            if sg_for_t_minus1 < 0:
                continue
            if (sg_for_t_minus1, None) not in model.c.index_set():
                # We'll handle the check inside the loop
                pass
            for k in model.S0:
                if (sg_for_t_minus1, k) in model.c.index_set():
                    for (l, l_next) in consecutive_scenarios(model, sg_for_t_minus1, k):
                        if (t, l) in var_obj and (t, l_next) in var_obj:
                            idx.append((var_name, t, k, l, l_next))
    return idx

def nac_fd_battery_rule(m, var_name, t, k, l, l_next):
    var_obj = getattr(m, var_name)
    return var_obj[t, l] == var_obj[t, l_next]

model.NAC_fd_battery_index = pyo.Set(dimen=5, initialize=build_nac_fd_battery_index)
model.NAC_fd_battery = pyo.Constraint(model.NAC_fd_battery_index, rule=nac_fd_battery_rule)