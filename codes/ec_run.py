# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 11:06:23 2025

@author: andre
"""

# =============================================================================
# Pyomo translation of ec_run.py
# 
# A Python script replicating ec.run
# when using a Pyomo AbstractModel defined in ec_model.py.
# 
# =============================================================================

import os
import math
import time
import pyomo.environ as pyo
from pyomo.environ import DataPortal, value, SolverFactory
from pathlib import Path
import importlib
import yaml
import json
# ---------------------------------------------------------------------
# Read in configuration from 
# ---------------------------------------------------------------------

# Run mode options:
#   'observed'  -> perfect foresight using ScenO
#   'forecasted'-> single forecast scenario using ScenF
#   'expected'  -> using aggregated expected scenario from Scen0 using ScenE
#   'multiscen' -> full tree simulation using Scen0 (default)


config_path = Path(__file__).parent / "config.yaml"
with open(config_path) as f:
    cfg = yaml.safe_load(f)

MODE = cfg['MODE']

BESS_datfile   = cfg["BESS_datfile"]
wind_datfile   = cfg["wind_datfile"]
market_datfile = cfg["market_datfile"]
hydrogen_datfile = cfg["hydrogen_datfile"]
PROB  = cfg["PROB"]
probl = cfg["probl"]

project_root = Path(cfg["project_root"]).expanduser() 

famscen = cfg["famscen"]
include_h2   = cfg["include_h2"]
n_days  = cfg["n_days"]

SIMS = [f"{i:03d}" for i in range(1, n_days + 1)]  

pathscen = f"scenarios/{famscen}/"
pathdem  = cfg["pathdem"]
pathdem_h2 = cfg["pathdem_h2"]
pathres       = None   # set inside loop
pathmarketres = None   # set inside loop

resfile      = cfg["resfile"]
profitfile = {p: f"profit_{p}.txt" for p in PROB}
timefile = {p: f"time_{p}.txt"   for p in PROB}
timefileFull = cfg["timefileFull"]
numscenfile  = cfg["numscenfile"]



print("\n########################")
print(f"#### Problem {probl}")
print("########################\n")


solve_time = {}
n_scenarios = {}

# load the model, with or without hydrogen
if include_h2:
    module_name = f"models.ec_hydrogen_model"
else:
    module_name = f"models.ec_model"
abstract_model = importlib.import_module(module_name).model

# obj function keys:
if include_h2:
    obj_results = {key: {} for key in [
    "obj_fun", "obj_DA_income", "obj_RM_income", "obj_IM_income",
    "obj_IB_income", "obj_H2_income", "obj_H2_DEM", "obj_IB_costs", "obj_IB_net", "obj_FD_costs", "obj_BESS_costs",
    "obj_wat_costs", "obj_warm_st_costs", "obj_cold_st_costs", "obj_deg_EL_costs",
    "obj_warm_st_costs_FC", "obj_cold_st_costs_FC", "obj_deg_FC_costs"
]}
else:
    obj_results = {key: {} for key in [
    "obj_fun", "obj_DA_income", "obj_RM_income", "obj_IM_income", "obj_BESS_costs",
    "obj_IB_income", "obj_IB_costs", "obj_IB_net", "obj_FD_costs"
]}


solve_time = {}
n_scenarios = {}

# ---------------------------------------------------------------------
# 3) For each sim in SIMS, replicate the logic in ec.run
# ---------------------------------------------------------------------
for sim in SIMS:
    # Print messages like AMPL:
    print("\n########################")
    print(f"#### Instance {probl}-{sim}")
    print("########################\n")

    pathres       = f"results/{famscen}/{probl}/{sim}/"
    pathmarketres = f"results/{famscen}/market/{sim}/"
    
    # Ensure pathres and pathmarketres exist before writing files
    os.makedirs(os.path.join(project_root, pathres), exist_ok=True)
    os.makedirs(os.path.join(project_root, pathmarketres), exist_ok=True)

    # let scenfile := famscen&"-"&sim&".dat";
    scenfile = f"{famscen}.json"
    print(f"scenfile path = {pathscen}{scenfile}")
    print(f"pathres        = {pathres}")

    # let demfile := "demand-"&sim&".dat";
    demfile = f"demand-{sim}.dat"
    print(f"demfile path   = {pathdem}{demfile}")
    print(f"pathres        = {pathres}")

    demfile_h2 = f"demand_h2-{sim}.dat"
    print(f"demfile_h2 path   = {pathdem_h2}{demfile_h2}")
    print(f"pathres        = {pathres}")
    
    scenario_data = DataPortal()
    # Load the "base" data 
    scenario_data.load(filename=os.path.join(project_root, "data", market_datfile),  model=abstract_model)
    scenario_data.load(filename=os.path.join(project_root, "data", BESS_datfile),    model=abstract_model)
    scenario_data.load(filename=os.path.join(project_root, "data", wind_datfile),    model=abstract_model)
    if include_h2:
        scenario_data.load(filename=os.path.join(project_root, "data", hydrogen_datfile), model=abstract_model)

    # Then load scenario & demand data
    #scenario_data.load(filename=os.path.join(project_root, pathscen, scenfile), model=abstract_model)
    with open(os.path.join(project_root, pathscen, scenfile)) as f:
        scen = json.load(f)[int(sim)-1]
    scenario_data["ScenF"] = {i+1: v for i, v in enumerate(scen["predicted_value"])}
    scenario_data["ScenO"]  = {i+1: v for i, v in enumerate(scen["observed_value"])} if scen["observed_value"] else {}
    #scenario_data["Scen0"]  = {i+1: v for i, v in enumerate(scen["mean_scenarios"])}
    scenario_data["Scen0"] = {
        (rv, s): scen["scenario_tree_data"][s - 1][rv - 1]
        for s in range(1, len(scen["scenario_tree_data"]) + 1)
        for rv in range(1, len(scen["scenario_tree_data"][s - 1]) + 1)
    }

    scenario_data["c"] = {
        (entry["key"][0], entry["key"][1]): entry["scenario_ids"]
        for entry in scen["tree"]
    }
    scenario_data["nS"]  = {None: scen["num_scenarios"]}   
    scenario_data["nSG"] = {None: scen["num_stages"]} 
    #scenario_data["nRVSG"] = {row[0]: row[1] for row in scen["nRVSG"]}
    #scenario_data["nRVSG"] = {row["stages"][0]: len(row["columns"]) for row in scen["mapping_datasets_columns"]}
    nrvsg = {}
    for dataset in scen["mapping_datasets_columns"]:
        for i in dataset["stages"]:
            if nrvsg.get(i):
                nrvsg[i] += 1
            else:
                nrvsg[i] = 1

    scenario_data["nRVSG"] = nrvsg



    scenario_data.load(filename=os.path.join(project_root, pathdem,  demfile),  model=abstract_model)
    if include_h2:
        scenario_data.load(filename=os.path.join(project_root, pathdem_h2,  demfile_h2),  model=abstract_model)
    print(f"\nT = {scenario_data['nT']}, nS = {scenario_data['nS']}, nIM = {scenario_data['nIM']}")
    
    "Before creating the instance"
    # Some Data Preprocess needed before creating the instance because these values are used to build sets in model.py, so they must be defined before creating the instance
    #Prob0_raw = scenario_data.data().get("Prob0", {})
    Prob0_raw =  {i+1:scen["scenario_probabilities"][i] for i in range(scen["num_scenarios"])}    # scen["scenario_probabilities"]
    Scen0_raw = scenario_data.data().get("Scen0", {})
    ScenF_raw = scenario_data.data().get("ScenF", {})
    ScenO_raw = scenario_data.data().get("ScenO", {})

    # Scenario selection
    if MODE == 'observed':
        s_id = 1
        scenario_data.data()['S']    = {None: [s_id]}
        scenario_data.data()['Prob'] = {s_id: 1.0}
        Scen_preserved = { (rv, s_id): val for rv, val in ScenO_raw.items() }
        scenario_data.data()['Scen'] = Scen_preserved
        print("Mode=observed → using ScenO (perfect foresight)")

    elif MODE == 'forecasted':
        s_id = 1
        scenario_data.data()['S']    = {None: [s_id]}
        scenario_data.data()['Prob'] = {s_id: 1.0}
        Scen_preserved = { (rv, s_id): val for rv, val in ScenF_raw.items() }
        scenario_data.data()['Scen'] = Scen_preserved
        print("Mode=forecasted → using ScenF (forecast)")

    elif MODE == 'expected':
        # Compute and use the expected-value scenario from the scenario tree Scen0
        s_id = 1
        # Build expected scenario by averaging across all tree branches
        ScenE = {}
        for rv in set(rv for (rv, _) in Scen0_raw.keys()):
            ScenE[rv] = sum(Prob0_raw[s] * Scen0_raw.get((rv, s), 0.0) for s in Prob0_raw)
        scenario_data.data()['S']    = {None: [s_id]}
        scenario_data.data()['Prob'] = {s_id: 1.0}
        Scen_preserved = { (rv, s_id): val for rv, val in ScenE.items() }
        scenario_data.data()['Scen'] = Scen_preserved
        print("Mode=expected → using aggregated expected scenario from Scen0")

    else:
        S_preserved = [s for s, p in Prob0_raw.items() if p > 0]
        scenario_data.data()['S']    = {None: S_preserved}
        scenario_data.data()['Prob'] = {s: Prob0_raw[s] for s in S_preserved}
        Scen_preserved = { (rv, s): Scen0_raw[(rv, s)] for (rv, s) in Scen0_raw.keys() if s in S_preserved }
        scenario_data.data()['Scen'] = Scen_preserved
        print(f"Mode=multiscen → using Scen0 with scenarios {S_preserved}")

    # lD allocation
    lD_preserved = {}
    for t in range(1, scenario_data['nT']+1):
        for s in scenario_data.data()['S'][None]:
            lD_preserved[(t, s)] = scenario_data.data()['Scen'].get((t, s), 0.0)
    scenario_data.data()['lD'] = lD_preserved

    "Instance creation"
    instance = abstract_model.create_instance(scenario_data)
    print(f"Instance Variables: {len(list(instance.component_objects(pyo.Var)))}")
    print(f"Instance Constraints: {len(list(instance.component_objects(pyo.Constraint)))}")
    if hasattr(instance, 'var_fd'):
        print(f"var_fd size: {len(list(instance.var_fd.keys()))}")  # Should be 24
    print(f"T size: {len(list(instance.T))}")  # Should be 24
    print(f"S size: {len(list(instance.S))}")  # Should be 10
    
    "After creating the instance but before running the solver other parameters must be allocated"                                                  
    # Compute scenario cluster (c)
    c_filtered = {}
    
    for sg in instance.SG0:
        for s in instance.S0:
            c_filtered[(sg, s)] = [sc for sc in instance.c[sg, s] if sc in instance.S]
    # Store filtered clusters back into Pyomo model
    for (sg, s), cluster in c_filtered.items():
        instance.c[sg, s] = sorted(cluster)
    
    # Compute Expected Scenario (ScenE)
    ScenE_dict = {}
    
    # for rv in range(1, value(instance.nRV) + 1):  # Loop over all random variables
    #     ScenE_dict[rv] = sum(value(instance.Prob0[s_]) * value(instance.Scen0[rv, s_]) for s_ in instance.S0)
    # # Store into Pyomo model (ScenE is mutable, so we can assign values)
    # for rv, val in ScenE_dict.items():
    #     instance.ScenE[rv] = val

    # Compute pW and pPV     
    pW_dict = {}
    pPV_dict = {}
    mean_pW_dict = {}
    mean_pPV_dict = {}
    sigma_pW_dict = {}
    
    for t in instance.T:
        for s in instance.S:
            # Fetch the correct random variable index from fRVSG
            rv_index_wind = value(instance.fRVSG[value(instance.sgpw[t])])
            rv_index_solar = rv_index_wind + 1  # Next variable corresponds to PV
            # Compute wind power
            pW_dict[(t, s)] = min(value(instance.Scen[rv_index_wind, s]), 1.0) * value(instance.P_W)            
            # Compute PV power
            pPV_dict[(t, s)] = min(value(instance.Scen[rv_index_solar, s]), 1.0) * value(instance.P_PV)
    # Compute mean values
    for t in instance.T:
        mean_pW_dict[t] = sum(value(instance.Prob[s]) * pW_dict[(t, s)] for s in instance.S)
        mean_pPV_dict[t] = sum(value(instance.Prob[s]) * pPV_dict[(t, s)] for s in instance.S)
    # Compute sigma_pW (standard deviation)
    for t in instance.T:
        variance_pW = sum(value(instance.Prob[s]) * (pW_dict[(t, s)] - mean_pW_dict[t]) ** 2 for s in instance.S)
        sigma_pW_dict[t] = math.sqrt(variance_pW)
    # Store values in Pyomo model
    for (t, s), val in pW_dict.items():
        instance.pW[t, s] = max(val, 0)
    for (t, s), val in pPV_dict.items():
        instance.pPV[t, s] = max(val, 0)
    for t, val in mean_pW_dict.items():
        instance.mean_pW[t] = max(val, 0)
    for t, val in mean_pPV_dict.items():
        instance.mean_pPV[t] = max(val, 0)
    for t, val in sigma_pW_dict.items():
        instance.sigma_pW[t] = max(val, 0)   
    
    # Compute max values for wind and solar power    
    mean_pW_avg  = sum(mean_pW_dict[t] for t in instance.T) / value(instance.nT)
    mean_pPV_avg  = sum(mean_pPV_dict[t] for t in instance.T) / value(instance.nT)
    max_pW = max(value(instance.pW[t, s]) for t in instance.T for s in instance.S)
    max_pPV = max(value(instance.pPV[t, s]) for t in instance.T for s in instance.S)
    # Store max values in Pyomo model
    instance.max_pW = max_pW
    instance.max_pPV = max_pPV
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write(f"max_pW: {max_pW}, max_pPV: {max_pPV}\n")
    print(f"max_pW: {max_pW}, mean_pW: {mean_pW_avg}, max_pPV: {max_pPV}, mean_pPV: {mean_pPV_avg}")

    # Cardinality of S0 and S
    card_S0 = len(instance.S0)
    card_S = len(instance.S)
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\n Cardinality of the problem:\n")
        res_log.write(f"card(S0): {card_S0}\n")
        res_log.write(f"card(S): {card_S}\n")
    print(f"card(S0): {card_S0}, card(S): {card_S}") 

    # Compute nearest tree scenario to the observed scenario ScenO: dTO and sOR              
    dTO_dict = {}
    min_dTO = 10**10  # Large initial value
    sOR = -1  # Default value
    for s in instance.S:
        dTO_dict[s] = math.sqrt(sum((value(instance.Scen[rv, s]) - value(instance.ScenO[rv])) ** 2 for rv in range(1, value(instance.nRV) + 1)))
    # Find the scenario with the minimum distance
    for s in instance.S:
        if dTO_dict[s] < min_dTO:
            min_dTO = dTO_dict[s]
            sOR = s
    # Store in Pyomo model
    instance.min_dTO = min_dTO
    instance.sOR = sOR
    # Log nearest tree scenario
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\n Nearest Tree scenario, Observed data:\n")
        res_log.write(f"sOR: {sOR}\n")
        res_log.write(f"min_dTO: {min_dTO}\n")
    print(f"Nearest Tree Scenario: sOR={sOR}, min_dTO={min_dTO}")

    # =============================================================================
    #     Next Initial conditions update
    # =============================================================================
    if sim == SIMS[0]:
        prev_sOR = None
        
    if sim != SIMS[0]:

        def read_last_value(file_path, scenario, tol=1e-5):
            """
            Read the last column for 'scenario' from a file whose lines look like:
               <scenario> <prob> v1 v2 ... vN
            Return vN as an int if it’s within 'tol' of an integer, else as a float.
            """
            with open(file_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if parts[0] == str(scenario):
                        val = float(parts[-1])
                        # if val is within tol of an integer, snap it
                        nearest = round(val)
                        if abs(val - nearest) < tol:
                            return int(nearest)
                        return val
            raise KeyError(f"Scenario {scenario} not found in {file_path}")

        
        # compute previous‐day code, e.g. '002'→'001', '010'→'009'
        prev_sim = f"{int(sim)-1:03d}"
        prev_res = f"results/{famscen}/{probl}/{prev_sim}"
        # paths to yesterday’s exports
        bess_file = os.path.join(project_root, prev_res, "BESS")
        hyd_dir   = os.path.join(project_root, prev_res, "HYD")

        # read the last‐hour values for our chosen scenario sOR
        instance.SOCini      = read_last_value(os.path.join(bess_file,"socV.txt"), prev_sOR)
        if include_h2:
            instance.LOH_ini     = read_last_value(os.path.join(hyd_dir,"LOH.txt"),    prev_sOR)
            instance.iEL_on_ini  = read_last_value(os.path.join(hyd_dir,"iEL_on.txt"),  prev_sOR)
            instance.iEL_sb_ini  = read_last_value(os.path.join(hyd_dir,"iEL_sb.txt"),  prev_sOR)
            instance.iEL_off_ini = read_last_value(os.path.join(hyd_dir,"iEL_off.txt"), prev_sOR)
            instance.iFC_on_ini  = read_last_value(os.path.join(hyd_dir,"iFC_on.txt"),  prev_sOR)
            instance.iFC_sb_ini  = read_last_value(os.path.join(hyd_dir,"iFC_sb.txt"),  prev_sOR)
            instance.iFC_off_ini = read_last_value(os.path.join(hyd_dir,"iFC_off.txt"), prev_sOR)
        
        # Log the new initial conditions
        with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
            res_log.write("\nNew initial conditions:\n")
            res_log.write(f"SOCini: {value(instance.SOCini)}\n")
            res_log.write(f"sOR: {value(instance.sOR)}\n")
            if include_h2:
                res_log.write(f"LOH_ini: {value(instance.LOH_ini)}\n")
                res_log.write(f"iEL_on_ini: {value(instance.iEL_on_ini)}\n")
                res_log.write(f"iEL_sb_ini: {value(instance.iEL_sb_ini)}\n")
                res_log.write(f"iEL_off_ini: {value(instance.iEL_off_ini)}\n")
                res_log.write(f"iFC_on_ini: {value(instance.iFC_on_ini)}\n")
                res_log.write(f"iFC_sb_ini: {value(instance.iFC_sb_ini)}\n")
                res_log.write(f"iFC_off_ini: {value(instance.iFC_off_ini)}\n")

        
        # Print new initial conditions to console
        print(f"New Initial Conditions:")
        print(f"SOCini: {value(instance.SOCini)}")
        if include_h2:
            print(f"LOH_ini: {value(instance.LOH_ini)}, iEL_on_ini: {value(instance.iEL_on_ini)}, iEL_sb_ini: {value(instance.iEL_sb_ini)}, iEL_off_ini: {value(instance.iEL_off_ini)}, iFC_on_ini: {value(instance.iFC_on_ini)}, iFC_sb_ini: {value(instance.iFC_sb_ini)}, iFC_off_ini: {value(instance.iFC_off_ini)}, sOR: {value(instance.sOR)}")

    else:
        # Day 1: leave the .dat‐provided iEL_*_ini untouched
        print("Day 1 — using default initial electrolyzer and fuel cell state from .dat")  
    
    prev_sOR = sOR
    
    # Reset IM bid bounds and auxiliary parameters
    SSG_dict = {sg: set() for sg in instance.SG0}  # Representative scenarios per stage
    probc_dict = {}  # Probability of clusters
    mean_pWc_dict = {}  # Conditional mean wind power
    # Identify representative scenarios at each stage sg
    for sg in instance.SG0:
        SSG_dict[sg] = sorted({s for s in instance.S0 if len(instance.c[sg, s]) > 0})
    # Compute probability of cluster c[sg, sc]
    for sg in instance.SG0:
        for sc in SSG_dict[sg]:
            probc_dict[sg, sc] = sum(value(instance.Prob[s]) for s in instance.c[sg, sc])
    # Store computed values into the Pyomo model
    for sg, scenarios in SSG_dict.items():
        instance.SSG[sg] = scenarios
        
    # # Compute conditional mean wind power for every cluster
    # for sg in instance.SG0:
    #     for sc in SSG_dict[sg]:
    #         for t in instance.T:
    #             if probc_dict.get((sg, sc), 0) > 0:
    #                 mean_pWc_dict[sg, sc, t] = sum(value(instance.Prob[s]) * value(instance.pW[t, s]) for s in instance.c[sg, sc]) / probc_dict[sg, sc]
    
    # for (sg, sc), val in probc_dict.items():
    #     instance.probc[sg, sc] = val
    # for (sg, sc, t), val in mean_pWc_dict.items():
    #     instance.mean_pWc[sg, sc, t] = val
    
    # # Create dictionaries to store computed values
    # meanmax_pVI_RP_dict = {}
    # meanmin_pVI_RP_dict = {}
    # meanmax_pVI_EV_dict = {}
    # meanmin_pVI_EV_dict = {}
    
    # # Compute bounds for pVI deviations in RP and EV problems
    # for i in instance.IM:
    #     for t in instance.TIM[i]:
    #         # Loop over clusters at stage (sgim[i] - 1)
    #         for sc in instance.SSG[instance.sgim[i] - 1]:
    #             sg_stage = instance.sgim[i] - 1
    
    #             # Compute max and min deviations for pW[t,s]
    #             numerator_max = sum(
    #                 value(instance.Prob[s]) * (value(instance.pW[t, s]) - value(instance.mean_pW[t]))
    #                 for s in instance.c[sg_stage, sc]
    #                 if value(instance.pW[t, s]) - value(instance.mean_pW[t]) > 0
    #             )
    #             numerator_min = sum(
    #                 value(instance.Prob[s]) * (value(instance.pW[t, s]) - value(instance.mean_pW[t]))
    #                 for s in instance.c[sg_stage, sc]
    #                 if value(instance.pW[t, s]) - value(instance.mean_pW[t]) < 0
    #             )
    
    #             meanmax = numerator_max / value(instance.probc[sg_stage, sc]) if value(instance.probc[sg_stage, sc]) > 0 else 0.0
    #             meanmin = numerator_min / value(instance.probc[sg_stage, sc]) if value(instance.probc[sg_stage, sc]) > 0 else 0.0
    
    #             # Store computed deviations
    #             for s in instance.c[sg_stage, sc]:
    #                 meanmax_pVI_RP_dict[i, t, s] = meanmax
    #                 meanmin_pVI_RP_dict[i, t, s] = meanmin
    
    #         # Compute and store EV bounds
    #         meanmax_pVI_EV_dict[i, t] = sum(
    #             value(instance.probc[instance.sgim[i] - 1, sc]) * meanmax_pVI_RP_dict[i, t, next(iter(instance.c[instance.sgim[i] - 1, sc]))]
    #             for sc in instance.SSG[instance.sgim[i] - 1]
    #         )
    #         meanmin_pVI_EV_dict[i, t] = sum(
    #             value(instance.probc[instance.sgim[i] - 1, sc]) * meanmin_pVI_RP_dict[i, t, next(iter(instance.c[instance.sgim[i] - 1, sc]))]
    #             for sc in instance.SSG[instance.sgim[i] - 1]
    #         )

    # # Store computed values into Pyomo model
    # for (i, t, s), val in meanmax_pVI_RP_dict.items():
    #     instance.meanmax_pVI_RP[i, t, s] = val
    # for (i, t, s), val in meanmin_pVI_RP_dict.items():
    #     instance.meanmin_pVI_RP[i, t, s] = val
    # for (i, t), val in meanmax_pVI_EV_dict.items():
    #     instance.meanmax_pVI_EV[i, t] = val
    # for (i, t), val in meanmin_pVI_EV_dict.items():
    #     instance.meanmin_pVI_EV[i, t] = val

    # Compute bounds for imbalance bids
    PIB_p_dict = {}
    PIB_m_dict = {}
    for t in instance.T:
        for s in instance.S:
            imbalance_p = value(instance.pW[t, s]) + value(instance.pPV[t, s]) - value(instance.mean_pW[t]) - value(instance.mean_pPV[t])
            PIB_p_dict[(t, s)] = imbalance_p if imbalance_p >= 0 else 0.0
            PIB_m_dict[(t, s)] = -imbalance_p if imbalance_p < 0 else 0.0
    # Store computed values into Pyomo model
    for (t, s), val in PIB_p_dict.items():
        instance.PIB_p[t, s] = val
    for (t, s), val in PIB_m_dict.items():
        instance.PIB_m[t, s] = val

    # Compute market prices (Day-Ahead prices already defined before creating the instance)
    lR_dict = {}
    lI_dict = {}
    lIB_dict = {}
    # Assign values to dictionaries
    for t in instance.T:
        for s in instance.S:
            # Reserve market prices
            lR_dict[t, s] = value(instance.Scen[value(instance.nT) + t, s])
            # System imbalance prices
            lIB_dict[t, s] = value(instance.Scen[value(instance.fRVSG[value(instance.nSG)]) + (t - 1), s])
    # Assign Intraday Market prices
    for i in instance.IM:
        for t in instance.TIM[i]:
            for s in instance.S:
                lI_dict[i, t, s] = value(instance.Scen[value(instance.fRVSG[value(instance.sgim[i])]) + t - min(instance.TIM[i]), s])
    # Store values in Pyomo instance
    for (t, s), val in lR_dict.items():
        instance.lR[t, s] = val
    for (i, t, s), val in lI_dict.items():
        instance.lI[i, t, s] = val
    for (t, s), val in lIB_dict.items():
        instance.lIB[t, s] = val

    # Compute mean market prices (the average value across all scenarios for each hour)
    mean_lD_dict = {}
    mean_lR_dict = {}
    mean_lI_dict = {}
    mean_lIB_dict = {}
    # Compute mean values
    for t in instance.T:
        mean_lD_dict[t]  = sum(value(instance.Prob[s]) * value(instance.lD[t, s]) for s in instance.S)
        mean_lR_dict[t]  = sum(value(instance.Prob[s]) * value(instance.lR[t, s]) for s in instance.S)
        mean_lIB_dict[t] = sum(value(instance.Prob[s]) * value(instance.lIB[t, s]) for s in instance.S)
    # Compute mean values for intraday markets
    for i in instance.IM:
        for t in instance.TIM[i]:
            mean_lI_dict[i, t] = sum(value(instance.Prob[s]) * value(instance.lI[i, t, s]) for s in instance.S)
    
    # Store values in Pyomo instance
    for t, val in mean_lD_dict.items():
        instance.mean_lD[t] = val
    for t, val in mean_lR_dict.items():
        instance.mean_lR[t] = val
    for (i, t), val in mean_lI_dict.items():
        instance.mean_lI[i, t] = val 
    for t, val in mean_lIB_dict.items():
        instance.mean_lIB[t] = val
        
    
    # === PRINT RESULTS ===
    # print("\n##### mean_lD (Day-Ahead Prices) #####")
    # for t, val in mean_lD_dict.items():
    #     print(f"mean_lD[{t}] = {val}")
    
    # print("\n##### mean_lR (Reserve Market Prices) #####")
    # for t, val in mean_lR_dict.items():
    #     print(f"mean_lR[{t}] = {val}")
    
    # print("\n##### mean_lI (Intraday Market Prices) #####")
    # for i in instance.IM:
    #     print(f"\n--- Intraday Market {i} ---")
    #     for t in instance.TIM[i]:
    #         print(f"mean_lI[{i}, {t}] = {mean_lI_dict[i, t]}")
    
    # print("\n##### mean_lIB (System Imbalance Prices) #####")
    # for t, val in mean_lIB_dict.items():
    #     print(f"mean_lIB[{t}] = {val}")
    
    # Compute and display mean values (the average value across all scenarios for all hours)
    mean_lD_avg  = sum(mean_lD_dict[t] for t in instance.T) / value(instance.nT)
    mean_lR_avg  = sum(mean_lR_dict[t] for t in instance.T) / value(instance.nT)
    mean_lIB_avg = sum(mean_lIB_dict[t] for t in instance.T) / value(instance.nT)

    # Compute average per intraday market (per i)
    mean_lI_avg_per_market = {}
    for i in instance.IM:
        t_list = list(instance.TIM[i])
        mean_lI_avg_per_market[i] = sum(mean_lI_dict[i, t] for t in t_list) / len(t_list)
    
    # Compute total average across all intraday markets (global average)
    total_sum_lI = sum(mean_lI_dict[i, t] for i in instance.IM for t in instance.TIM[i])
    total_TIM = sum(len(instance.TIM[i]) for i in instance.IM)
    mean_lI_global_avg = total_sum_lI / total_TIM

    # Write results to file
    with open(os.path.join(project_root, pathres, resfile), "a") as res_out:
        res_out.write("\nMean Values:\n")
        res_out.write(f"mean_lD_avg  = {mean_lD_avg:.6f}\n")
        res_out.write(f"mean_lR_avg  = {mean_lR_avg:.6f}\n")
        res_out.write(f"mean_lIB_avg = {mean_lIB_avg:.6f}\n")
        res_out.write(f"mean_pW_avg  = {mean_pW_avg:.6f}\n")
        res_out.write(f"mean_pPV_avg  = {mean_pW_avg:.6f}\n")
    
    # Compute positive and negative imbalance prices
    lPIB_dict = {}
    lNIB_dict = {}                   
    for t in instance.T:
        for s in instance.S:
            lIB_val = value(instance.lIB[t, s])
            lD_val = value(instance.lD[t, s])
            if lIB_val <= 1:
                lPIB_dict[(t, s)] = min(180.3, lIB_val * lD_val)
                lNIB_dict[(t, s)] = lD_val
            else:
                lPIB_dict[(t, s)] = lD_val
                lNIB_dict[(t, s)] = min(180.3, lIB_val * lD_val)
    # Store computed values in Pyomo model
    for (t, s), val in lPIB_dict.items():
        instance.lPIB[t, s] = val
    for (t, s), val in lNIB_dict.items():
        instance.lNIB[t, s] = val
    
    # Compute mean values for imbalance prices
    mean_lPIB_dict = {t: sum(value(instance.Prob[s]) * lPIB_dict[(t, s)] for s in instance.S) for t in instance.T}
    mean_lNIB_dict = {t: sum(value(instance.Prob[s]) * lNIB_dict[(t, s)] for s in instance.S) for t in instance.T}
    
    # Store computed values in Pyomo model
    for t, val in mean_lPIB_dict.items():
        instance.mean_lPIB[t] = val
    for t, val in mean_lNIB_dict.items():
        instance.mean_lNIB[t] = val

    # === PRINT RESULTS ===
    # print("\n##### Positive imbalance prices #####")
    # for t, val in mean_lPIB_dict.items():
    #     print(f"mean_lPIB[{t}] = {val}")
      
    # print("\n##### Negative imbalance prices #####")
    # for t, val in mean_lNIB_dict.items():
    #     print(f"mean_lNIB[{t}] = {val}")

    # Compute the average values
    mean_lPIB_avg = sum(mean_lPIB_dict[t] for t in instance.T) / value(instance.nT)
    mean_lNIB_avg = sum(mean_lNIB_dict[t] for t in instance.T) / value(instance.nT)
    
    # Print average market prices
    print("\nMean Values:")
    print(f"mean_lD_avg  = {mean_lD_avg:.6f}")
    print(f"mean_lR_avg  = {mean_lR_avg:.6f}")
    print(f"mean_lIB_avg = {mean_lIB_avg:.6f} (used to calculate pos. and neg. imb. prices)")
    # Print average per intraday market
    for i in instance.IM:
        print(f"mean_lI_avg for IM[{i}] = {mean_lI_avg_per_market[i]:.6f}")
    # Print global average for intraday market
    print(f"mean_lI_global_avg (all IMs combined) = {mean_lI_global_avg:.6f}")
    # Print average imbalances prices
    print(f"mean_lPIB_avg  = {mean_lPIB_avg:.6f}")
    print(f"mean_lNIB_avg  = {mean_lNIB_avg:.6f}")
    

    # =============================================================================
    #     Solve the problem
    # =============================================================================
    
    print("\n\n#EC problem: \n\n")
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\n\n#EC problem: \n\n")

    # Display initial conditions
    print("Initial conditions:")
    print(f"SOCini: {value(instance.SOCini)}")
    print(f"sOR: {value(instance.sOR)}")
    if include_h2:
        print(f"LOHini: {value(instance.LOH_ini)}")
        print(f"iEL_on_ini: {value(instance.iEL_on_ini)}")
        print(f"iEL_sb_ini: {value(instance.iEL_sb_ini)}")
        print(f"iEL_off_ini: {value(instance.iEL_off_ini)}")     
        print(f"iFC_on_ini: {value(instance.iFC_on_ini)}")
        print(f"iFC_sb_ini: {value(instance.iFC_sb_ini)}")
        print(f"iFC_off_ini: {value(instance.iFC_off_ini)}")                                     
    
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\nInitial conditions:\n")
        res_log.write(f"SOCini: {value(instance.SOCini)}\n")
        res_log.write(f"sOR: {value(instance.sOR)}\n")
        if include_h2:
            res_log.write(f"LOH_ini: {value(instance.LOH_ini)}\n")
            res_log.write(f"iEL_on_ini: {value(instance.iEL_on_ini)}\n")
            res_log.write(f"iEL_sb_ini: {value(instance.iEL_sb_ini)}\n")
            res_log.write(f"iEL_off_ini: {value(instance.iEL_off_ini)}\n")
            res_log.write(f"iFC_on_ini: {value(instance.iFC_on_ini)}\n")
            res_log.write(f"iFC_sb_ini: {value(instance.iFC_sb_ini)}\n")
            res_log.write(f"iFC_off_ini: {value(instance.iFC_off_ini)}\n")

    # SOLVER OPTIONS
    solver_cfg = cfg.get("solver", {})
    solver = SolverFactory(solver_cfg.pop("name", "gurobi"))
    for key, val in solver_cfg.items():
        solver.options[key] = val


    print("Solving the optimization problem...")
    start_time = time.time()
    results = solver.solve(instance, tee=True)
    end_time = time.time()
    
    solve_elapsed_time = end_time - start_time  # Compute elapsed time
    print(f"Solve elapsed time: {solve_elapsed_time:.2f} seconds")
    
    print(f"DA Income: {sum(value(instance.Prob[s]) * value(instance.lD[t, s]) * (value(instance.eDA_p[t, s]) - value(instance.eDA_m[t, s])) for t in instance.T for s in instance.S)}")
    print(f"RM Income: {sum(value(instance.Prob[s]) * (value(instance.rD[t, s]) + value(instance.rU[t, s])) * value(instance.lR[t, s]) for t in instance.T for s in instance.S)}")
    print(f"IM Income: {sum(value(instance.Prob[s]) * sum(value(instance.lI[i, t, s]) * value(instance.eIM[i, t, s]) for i in instance.IMT[t]) for t in instance.T for s in instance.S)}")
    print(f"IB Income: {sum(value(instance.Prob[s]) * value(instance.lPIB[t, s]) * value(instance.pIB_p[t, s]) for t in instance.T for s in instance.S)}")
    print(f"IB Costs: {sum(value(instance.Prob[s]) * value(instance.lNIB[t, s]) * value(instance.pIB_m[t, s]) for t in instance.T for s in instance.S)}")
    print(f"FD Costs: {sum(value(instance.Prob[s]) * value(instance.C_FD) * (value(instance.var_afd_p[t, s]) + value(instance.var_afd_m[t, s])) for t in instance.T for s in instance.S)}")
    print(f"BESS ageing Costs: {sum(value(instance.Prob[s]) * ((value(instance.dV[t, s]) + value(instance.cV[t, s]))/(2 * value(instance.Emax))) * (value(instance.B_sp_cost) * value(instance.Emax) / value(instance.cyc_max))  for t in instance.T for s in instance.S)}")
    if include_h2:
        print(f"H2 Dem Income: {sum(value(instance.lambda_H) * value(instance.HDEM[t]) for t in instance.T)}")
        print(f"H2 Income: {sum(value(instance.Prob[s]) * value(instance.lambda_H) * value(instance.Hsold[t, s]) * value(instance.can_sell_H2) for t in instance.T for s in instance.S)}")                                                                                                                                                                                                                                                                                                                                                                              
        print(f"Water Costs: {sum(value(instance.Prob[s]) * value(instance.lambda_wat) * value(instance.sp_wat_EL) * value(instance.HEL[t, s]) for t in instance.T for s in instance.S)}")
        print(f"Warm startup Costs: {sum(value(instance.Prob[s]) * value(instance.lambda_warm_st) * value(instance.P_EL_nom) * value(instance.i_EL_warm[t, s]) for t in instance.T for s in instance.S)}")
        print(f"Cold startup Costs: {sum(value(instance.Prob[s]) * value(instance.lambda_cold_st) * value(instance.P_EL_nom) * value(instance.i_EL_cold[t, s]) for t in instance.T for s in instance.S)}")
        print(f"EL replacement Costs: {sum(value(instance.Prob[s]) * value(instance.EL_repl_cost) * value(instance.P_EL_nom) / value(instance.EL_lifetime) * value(instance.iEL_on[t, s]) for t in instance.T for s in instance.S)}")
        print(f"Warm startup Costs FC: {sum(value(instance.Prob[s]) * value(instance.lambda_warm_st_FC) * value(instance.P_FC_nom) * value(instance.i_FC_warm[t, s]) for t in instance.T for s in instance.S)}")
        print(f"Cold startup Costs FC: {sum(value(instance.Prob[s]) * value(instance.lambda_cold_st_FC) * value(instance.P_FC_nom) * value(instance.i_FC_cold[t, s]) for t in instance.T for s in instance.S)}")
        print(f"FC replacement Costs: {sum(value(instance.Prob[s]) * value(instance.FC_repl_cost) * value(instance.P_FC_nom) / value(instance.FC_lifetime) * value(instance.iFC_on[t, s]) for t in instance.T for s in instance.S)}")
        
        # Count electrolyzer on/standby/off hours
        hours_on   = sum(value(instance.iEL_on[t, s])  for t in instance.T for s in instance.S)
        hours_sb   = sum(value(instance.iEL_sb[t, s])  for t in instance.T for s in instance.S)
        hours_off  = sum(value(instance.iEL_off[t, s]) for t in instance.T for s in instance.S)
        print(f"Electrolyzer hours: ON={hours_on:.0f}, SB={hours_sb:.0f}, OFF={hours_off:.0f}")
        
        # Count fuel cell on/standby/off hours
        hours_on_FC   = sum(value(instance.iFC_on[t, s])  for t in instance.T for s in instance.S)
        hours_sb_FC   = sum(value(instance.iFC_sb[t, s])  for t in instance.T for s in instance.S)
        hours_off_FC  = sum(value(instance.iFC_off[t, s]) for t in instance.T for s in instance.S)
        print(f"Fuel cell hours: ON={hours_on_FC:.0f}, SB={hours_sb_FC:.0f}, OFF={hours_off_FC:.0f}")

    # =============================================================================
    # Results analysis
    # =============================================================================
    
    print(f"\nChecking non-anticipativity for Day {sim}")
    def consecutive_scenarios(model, sg, k):
        if (sg, k) not in model.c.index_set():
            return []
        # Sort using the same numeric key!
        scenario_list = sorted([l for l in model.c[sg, k] if l in model.S],
                               key=lambda x: int(x))
        return [(scenario_list[i], scenario_list[i+1]) for i in range(len(scenario_list)-1)]
    
    # List of all variables in non-anticipativity constraints
    if include_h2:
        nac_variables = [
            "eDA_p", "eDA_m", "ieDA_p",  # Day-Ahead Market
            "rU", "rU_B", "rU_FD", "rU_EL", "rU_FC",        # Reserve Market Upward
            "rD", "rD_B", "rD_FD", "rD_EL", "rD_FC"       # Reserve Market Downward
        ]
    else:
        nac_variables = [
        "eDA_p", "eDA_m", "ieDA_p",  # Day-Ahead Market
        "rU", "rU_B", "rU_FD",        # Reserve Market Upward
        "rD", "rD_B", "rD_FD",        # Reserve Market Downward
    ]

        
    # Iterate over all variables
    for var_name in nac_variables:
        if not hasattr(instance, var_name):  # Skip if variable not in model
            print(f"Skipping {var_name} (not found in model)")
            continue
    
        print(f"Checking NAC for {var_name}:")
        var = getattr(instance, var_name)  # Get the variable dynamically
    
        for t in instance.T:
            for k in instance.S0:
                for (l, l_next) in consecutive_scenarios(instance, 1, k):
                    try:
                        diff = abs(value(var[t, l]) - value(var[t, l_next]))
                        if diff > 1e-6:
                            print(f"Non-anticipativity violated: {var_name}[{t}, {l}] ≠ {var_name}[{t}, {l_next}]")
                    except KeyError:
                        print(f"Skipping {var_name}[{t}, {l}] or {var_name}[{t}, {l_next}] due to missing index")
    
    print(f"Checking NAC for pIB_p:")
    for t in instance.T:
        for k in instance.S0:
            sg_for_t = instance.sgpw[t]  # use the same stage as in the constraint
            for (l, l_next) in consecutive_scenarios(instance, sg_for_t, k):
                try:
                    diff = abs(value(instance.pIB_p[t, l]) - value(instance.pIB_p[t, l_next]))
                    if diff > 1e-6:
                        print(f"Non-anticipativity violated: pIB_p[{t}, {l}] ≠ pIB_p[{t}, {l_next}]")
                except KeyError:
                    print(f"Skipping pIB_p[{t}, {l}] or pIB_p[{t}, {l_next}] due to missing index")

    print(f"Checking NAC for pIB_m:")
    for t in instance.T:
        for k in instance.S0:
            sg_for_t = instance.sgpw[t]  # use the same stage as in the constraint
            for (l, l_next) in consecutive_scenarios(instance, sg_for_t, k):
                try:
                    diff = abs(value(instance.pIB_m[t, l]) - value(instance.pIB_m[t, l_next]))
                    if diff > 1e-6:
                        print(f"Non-anticipativity violated: pIB_m[{t}, {l}] ≠ pIB_m[{t}, {l_next}]")
                except KeyError:
                    print(f"Skipping pIB_m[{t}, {l}] or pIB_m[{t}, {l_next}] due to missing index")


    # List of all variables in non-anticipativity constraints
    if include_h2:
        nac_variables = [
            "var_fd", "var_afd_p", "var_afd_m",         # Flexible Demand
            "dV", "cV", "idV", "socV",                  # Battery Energy Storage
            "eEL", "eEL_on", "eEL_sb", "iEL_on", "iEL_sb", "iEL_off", "i_EL_warm", "i_EL_cold", "HEL", "HDIR_EL", "HCOMP_EL", # Electrolyzer
            "eCOMP", "HDIR_COMP", "HC_TK",              # Compressor
            "LOH", "HDISCH_TK", "HDIR_TK", "iTK",       # Storage tank
            "HFC", "eFC_on", "eFC_sb", "iFC_on", "iFC_sb", "iFC_off", "i_FC_warm", "i_FC_cold",                         # Fuel cell
            "Hsold"                                     # Hydrogen sold                                                                                                                                      
        ]
    else:
        nac_variables = [
            "var_fd", "var_afd_p", "var_afd_m",         # Flexible Demand
            "dV", "cV", "idV", "socV",                  # Battery Energy Storage                                                                                                                                 
        ]
    
    # Iterate over all variables
    for var_name in nac_variables:
        if not hasattr(instance, var_name):  # Skip if variable not in model
            print(f"Skipping {var_name} (not found in model)")
            continue
    
        print(f"Checking NAC for {var_name}:")
        var = getattr(instance, var_name)  # Get the variable dynamically
    
        for t in instance.T:
            for k in instance.S0:
                sg_for_t = instance.sgpw[t] - 1  # use the same stage as in the constraint
                for (l, l_next) in consecutive_scenarios(instance, sg_for_t, k):
                    try:
                        diff = abs(value(var[t, l]) - value(var[t, l_next]))
                        if diff > 1e-6:
                            print(f"Non-anticipativity violated: {var_name}[{t}, {l}] ≠ {var_name}[{t}, {l_next}]")
                    except KeyError:
                        print(f"Skipping {var_name}[{t}, {l}] or {var_name}[{t}, {l_next}] due to missing index")
    

    print(f"Checking NAC for all eIM:")
    # Check nonanticipativity for eIM using the same index logic as in build_nac_eIM_index:
    for i in instance.IM:
        for t in instance.TIM[i]:
            for k in instance.S0:
                sg_for_i = instance.sgim[i] - 1
                for (l, l_next) in consecutive_scenarios(instance, sg_for_i, k):
                    try:
                        diff = abs(value(instance.eIM[i, t, l]) - value(instance.eIM[i, t, l_next]))
                        if diff > 1e-6:
                            print(f"Non-anticipativity violated: eIM[{i}, {t}, {l}] ≠ eIM[{i}, {t}, {l_next}]")
                    except KeyError:
                        print(f"Skipping eIM[{i}, {t}, {l}] or eIM[{i}, {t}, {l_next}] due to missing index")

    # Store results
    print("\n########################")
    print("###### Results #########")
    print("########################\n")
    
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\n########################\n")
        res_log.write("###### Results #########\n")
        res_log.write("########################\n\n")
    
        # Store solver results
        res_log.write(f"solve_message: {results.solver.message}\n")
        res_log.write(f"solve_result_num: {results.solver.status}\n")
        res_log.write(f"solve_result: {results.solver.termination_condition}\n")
        res_log.write(f"solve_elapsed_time: {solve_elapsed_time:.2f} seconds\n")
    
    instance.time[probl, sim] = solve_elapsed_time  # Assign elapsed time
    instance.num_scen[probl, sim] = len(instance.S)  # Store scenario count
    # Store elapsed time in dictionary
    solve_time[(probl, sim)] = solve_elapsed_time
    n_scenarios[(probl, sim)] = len(instance.S)
    
    print(f"solve_message: {results.solver.message}")
    print(f"solve_result_num: {results.solver.status}")
    print(f"solve_result: {results.solver.termination_condition}")
    print(f"solve_elapsed_time: {solve_elapsed_time:.2f} seconds")
    # print(f"Number of scenarios: {num_scenarios}")
    
    
    # Define the WP results directory
    wp_path = os.path.join(project_root, pathres, "WP/")
    os.makedirs(wp_path, exist_ok=True)
    
    # Store WP parameters
    wp_params_file = os.path.join(wp_path, "WP_params.txt")
    with open(wp_params_file, "w") as f:
        f.write("###### Printing Wind Power Plant Sets and Parameters #########\n\n")
        f.write(f"sgpw: {list(instance.sgpw.values())}\n")
        f.write(f"max_pW: {value(instance.max_pW)}\n")
        f.write(f"P_W: {value(instance.P_W)}\n")

    # Store pW values for each scenario
    pw_file = os.path.join(wp_path, "pW.txt")
    with open(pw_file, "w") as f:
        for s in instance.S:
            f.write(f"{s} {value(instance.Prob[s])} ")
            for t in instance.T:
                f.write(f"{value(instance.pW[t, s])} ")
            f.write("\n")

    # Define the PV results directory
    pv_path = os.path.join(project_root, pathres, "PV/")
    os.makedirs(pv_path, exist_ok=True)
    
    # Store PV parameters
    pv_params_file = os.path.join(pv_path, "PV_params.txt")
    with open(pv_params_file, "w") as f:
        f.write("###### Printing PV Sets and Parameters #########\n\n")
        f.write("sgpPV = \n")
        
        for t in instance.T:
            f.write(f"{t}: {value(instance.sgpw[t]) + 1}\n")
        
        f.write(f"P_PV: {value(instance.P_PV)}\n")

    # Store pPV values for each scenario
    ppv_file = os.path.join(pv_path, "pPV.txt")
    with open(ppv_file, "w") as f:
        for s in instance.S:
            f.write(f"{s} {value(instance.Prob[s])} ")
            for t in instance.T:
                f.write(f"{value(instance.pPV[t, s])} ")
            f.write("\n")
    

    # Function to export values of each variable in .txt files
    def export_variable(var, file_path, time_set):
        """
        Exports a Pyomo variable 'var' to 'file_path'.
        'time_set' is the set over which the variable is indexed in time (e.g., instance.T or instance.T0).
        Each line starts with the scenario and its probability, followed by the variable's values for each time period.
        """
        with open(file_path, "w") as f:
            for s in instance.S:
                # Build a list of string values for each time index        
                values_str = " ".join(str(value(var[t, s])) for t in time_set)
                f.write(f"{s} {value(instance.Prob[s])} {values_str}\n")

    # For a variable defined as a difference, you can also write:
    def export_diff(var1, var2, file_path, time_set):
        with open(file_path, "w") as f:
            for s in instance.S:
                diff_values = " ".join(str(value(var1[t, s] - var2[t, s])) for t in time_set)
                f.write(f"{s} {value(instance.Prob[s])} {diff_values}\n")

    # Save Flexible Demand Variables
    fd_path = os.path.join(project_root, pathres, "FD/")
    os.makedirs(fd_path, exist_ok=True)
    
    export_variable(instance.var_fd, os.path.join(fd_path, "var_fd.txt"), instance.T)
    export_variable(instance.var_afd_p, os.path.join(fd_path, "var_afd_p.txt"), instance.T)
    export_variable(instance.var_afd_m, os.path.join(fd_path, "var_afd_m.txt"), instance.T)
    
    # Store FD parameters and sets
    fd_params_file = os.path.join(fd_path, "FD_params.txt")
    with open(fd_params_file, "w") as f:
        f.write(f"nFI: {value(instance.nFI)}\n")
        f.write(f"FI: {list(instance.FI)}\n")
        
        for t in instance.T:
            f.write(f"FD[{t}]: {value(instance.FD[t])}\n")
            f.write(f"FD_L[{t}]: {value(instance.FD_L[t])}\n")
            f.write(f"FD_U[{t}]: {value(instance.FD_U[t])}\n")
            f.write(f"RUFD[{t}]: {value(instance.RUFD[t])}\n")
            f.write(f"RDFD[{t}]: {value(instance.RDFD[t])}\n")
        
        for f_ in instance.FI:
            f.write(f"TF_L[{f_}]: {value(instance.TF_L[f_])}\n")
            f.write(f"TF_U[{f_}]: {value(instance.TF_U[f_])}\n")
            f.write(f"coef_FD[{f_}]: {value(instance.coef_FD[f_])}\n")
    
        f.write(f"C_FD: {value(instance.C_FD)}\n")

    # Define the BESS results directory
    bess_path = os.path.join(project_root, pathres, "BESS/")
    os.makedirs(bess_path, exist_ok=True)
    
    # Store BESS parameters
    bess_params_file = os.path.join(bess_path, "BESS_params.txt")
    with open(bess_params_file, "w") as f:
        f.write("###### Printing BESS Parameters and Optimal Variables #########\n\n")
        f.write(f"Emax: {value(instance.Emax)}\n")
        f.write(f"Dmax: {value(instance.Dmax)}\n")
        f.write(f"RTE: {value(instance.RTE)}\n")
        f.write(f"SOCmax: {value(instance.SOCmax)}\n")
        f.write(f"SOCmin: {value(instance.SOCmin)}\n")
        f.write(f"SOCini: {value(instance.SOCini)}\n")
        f.write(f"SOCfin: {value(instance.SOCfin)}\n")
        f.write(f"cyc_max: {value(instance.cyc_max)}\n")
        f.write(f"B_sp_cost: {value(instance.B_sp_cost)}\n")

    # Export BESS variables
    export_variable(instance.dV, os.path.join(bess_path, "dV.txt"), instance.T)
    export_variable(instance.cV, os.path.join(bess_path, "cV.txt"), instance.T)
    export_variable(instance.idV, os.path.join(bess_path, "idV.txt"), instance.T)
    export_variable(instance.socV, os.path.join(bess_path, "socV.txt"), instance.T0)
    export_diff(instance.cV, instance.dV, os.path.join(bess_path, "cV-dV.txt"), instance.T)

    # Similarly for DA variables:
    da_path = os.path.join(project_root, pathmarketres, "DA/")
    os.makedirs(da_path, exist_ok=True)
    
    export_variable(instance.lD, os.path.join(da_path, "lD.txt"), instance.T)
    export_variable(instance.eDA_p, os.path.join(da_path, "eDA_p.txt"), instance.T)
    export_variable(instance.eDA_m, os.path.join(da_path, "eDA_m.txt"), instance.T)
    export_variable(instance.ieDA_p, os.path.join(da_path, "ieDA_p.txt"), instance.T)
    export_variable(instance.ieDA_m, os.path.join(da_path, "ieDA_m.txt"), instance.T)
        
    # Define the RM results directory
    rm_path = os.path.join(project_root, pathmarketres, "RM/")
    os.makedirs(rm_path, exist_ok=True)
    
    # Export RM price variables (lR)
    export_variable(instance.lR, os.path.join(rm_path, "lR.txt"), instance.T)
    
    # Export RM parameter TSR (a single value)
    with open(os.path.join(rm_path, "RM_params.txt"), "w") as f:
        f.write(f"TSR: {value(instance.TSR)}\n")
    
    # Export RM variables
    export_variable(instance.rU, os.path.join(rm_path, "rU.txt"), instance.T)
    export_variable(instance.rU_B, os.path.join(rm_path, "rU_B.txt"), instance.T)
    export_variable(instance.rU_FD, os.path.join(rm_path, "rU_FD.txt"), instance.T)
    export_variable(instance.rD, os.path.join(rm_path, "rD.txt"), instance.T)
    export_variable(instance.rD_B, os.path.join(rm_path, "rD_B.txt"), instance.T)
    export_variable(instance.rD_FD, os.path.join(rm_path, "rD_FD.txt"), instance.T)
    if include_h2:
        export_variable(instance.rU_EL, os.path.join(rm_path, "rU_EL.txt"), instance.T)
        export_variable(instance.rU_FC, os.path.join(rm_path, "rU_FC.txt"), instance.T)
        export_variable(instance.rD_EL, os.path.join(rm_path, "rD_EL.txt"), instance.T)
        export_variable(instance.rD_FC, os.path.join(rm_path, "rD_FC.txt"), instance.T)


    # Print header for Intraday Market Parameters
    with open(os.path.join(project_root, pathmarketres, resfile), "a") as res_log:
        res_log.write("\n###### Printing Intraday Market Parameters and Optimal Variables #########\n\n")
    
    # Define the IM results directory
    im_path = os.path.join(project_root, pathmarketres, "IM/")
    os.makedirs(im_path, exist_ok=True)
    
    # IM Sets and Parameters (lI values for each i in IM)
    for i in instance.IM:
        li_file = os.path.join(im_path, f"lI_{i}.txt")
        with open(li_file, "w") as f:
            for s in instance.S:
                f.write(f"{s} {value(instance.Prob[s])} ")
                for t in instance.T:
                    if t in instance.TIM[i]:
                        f.write(f"{value(instance.lI[i, t, s])} ")
                    else:
                        f.write("0 ")
                f.write("\n")
    
    # Store IM parameter maxTIM
    im_params_file = os.path.join(im_path, "IM_params.txt")
    with open(im_params_file, "w") as f:
        f.write(f"maxTIM: {value(instance.maxTIM)}\n")
    
    # IM Variables (eIM values for each i in IM)
    for i in instance.IM:
        eim_file = os.path.join(im_path, f"eIM_{i}.txt")
        with open(eim_file, "w") as f:
            for s in instance.S:
                f.write(f"{s} {value(instance.Prob[s])} ")
                for t in instance.T:
                    if t in instance.TIM[i]:
                        f.write(f"{value(instance.eIM[i, t, s])} ")
                    else:
                        f.write("0 ")
                f.write("\n")
    
    # Compute total intraday market energy (eIM_TOT)
    eim_tot_dict = {}
    for t in instance.T:
        for s in instance.S:
            eim_tot_dict[(t, s)] = sum(value(instance.eIM[i, t, s]) for i in instance.IMT[t])
    
    # Store total IM energy (eIM_TOT)
    eim_tot_file = os.path.join(im_path, "eIM_TOT.txt")
    with open(eim_tot_file, "w") as f:
        for s in instance.S:
            f.write(f"{s} {value(instance.Prob[s])} ")
            for t in instance.T:
                f.write(f"{eim_tot_dict[(t, s)]} ")
            f.write("\n")
    
    # Print header for Imbalances Parameters
    with open(os.path.join(project_root, pathmarketres, resfile), "a") as res_log:
        res_log.write("\n###### Printing Imbalances Parameters and Optimal Variables #########\n\n")
    
    # Define the IB results directory
    ib_path = os.path.join(project_root, pathmarketres, "IB/")
    os.makedirs(ib_path, exist_ok=True)
    
    export_variable(instance.lPIB, os.path.join(ib_path, "lPIB.txt"), instance.T)
    export_variable(instance.lNIB, os.path.join(ib_path, "lNIB.txt"), instance.T)
    export_variable(instance.pIB_p, os.path.join(ib_path, "pIB_p.txt"), instance.T)
    export_variable(instance.pIB_m, os.path.join(ib_path, "pIB_m.txt"), instance.T)
    export_diff(instance.pIB_p, instance.pIB_m, os.path.join(ib_path, "pIB_p-pIB_m.txt"), instance.T)
    
    if include_h2:
        # Define the HYD results directory
        hyd_path = os.path.join(project_root, pathres, "HYD/")
        os.makedirs(hyd_path, exist_ok=True)
        
        # Store HYD parameters
        hyd_params_file = os.path.join(hyd_path, "HYD_params.txt")
        with open(hyd_params_file, "w") as f:
            f.write("###### Printing HYD Parameters and Optimal Variables #########\n\n")
            f.write(f"HDEM_press: {value(instance.HDEM_press)}\n")
            f.write(f"min_EL_frac: {value(instance.min_EL_frac)}\n")
            f.write(f"P_EL_nom: {value(instance.P_EL_nom)}\n")
            f.write(f"eta_EL: {value(instance.eta_EL)}\n")
            f.write(f"sp_wat_EL: {value(instance.sp_wat_EL)}\n")
            f.write(f"lambda_wat: {value(instance.lambda_wat)}\n")
            f.write(f"SB_frac: {value(instance.SB_frac)}\n")
            f.write(f"EL_lifetime: {value(instance.EL_lifetime)}\n")
            f.write(f"EL_repl_cost: {value(instance.EL_repl_cost)}\n")
            f.write(f"lambda_warm_st: {value(instance.lambda_warm_st)}\n")
            f.write(f"lambda_cold_st: {value(instance.lambda_cold_st)}\n")
            f.write(f"spec_COMP: {value(instance.spec_COMP)}\n")
            f.write(f"P_COMP_nom: {value(instance.P_COMP_nom)}\n")
            f.write(f"H_tank_cap: {value(instance.H_tank_cap)}\n")
            f.write(f"P_tank: {value(instance.P_tank)}\n")
            f.write(f"eta_tank: {value(instance.eta_tank)}\n")
            f.write(f"LOH_min: {value(instance.LOH_min)}\n")
            f.write(f"LOH_max: {value(instance.LOH_max)}\n")
            f.write(f"LOH_ini: {value(instance.LOH_ini)}\n")
            f.write(f"LOH_fin: {value(instance.LOH_fin)}\n")
            f.write(f"min_FC_frac: {value(instance.min_FC_frac)}\n")
            f.write(f"P_FC_nom: {value(instance.P_FC_nom)}\n")
            f.write(f"eta_FC: {value(instance.eta_FC)}\n")
            f.write(f"SB_frac_FC: {value(instance.SB_frac_FC)}\n")
            f.write(f"FC_lifetime: {value(instance.FC_lifetime)}\n")
            f.write(f"FC_repl_cost: {value(instance.FC_repl_cost)}\n")
            f.write(f"lambda_warm_st_FC: {value(instance.lambda_warm_st_FC)}\n")
            f.write(f"lambda_cold_st_FC: {value(instance.lambda_cold_st_FC)}\n")

        # Export HYD variables
        export_variable(instance.eEL, os.path.join(hyd_path, "eEL.txt"), instance.T)
        export_variable(instance.HEL, os.path.join(hyd_path, "HEL.txt"), instance.T)
        export_variable(instance.eEL_on, os.path.join(hyd_path, "eEL_on.txt"), instance.T)
        export_variable(instance.eEL_sb, os.path.join(hyd_path, "eEL_sb.txt"), instance.T)
        export_variable(instance.iEL_on, os.path.join(hyd_path, "iEL_on.txt"), instance.T)
        export_variable(instance.iEL_sb, os.path.join(hyd_path, "iEL_sb.txt"), instance.T)
        export_variable(instance.iEL_off, os.path.join(hyd_path, "iEL_off.txt"), instance.T)
        export_variable(instance.i_EL_warm, os.path.join(hyd_path, "i_EL_warm.txt"), instance.T)
        export_variable(instance.i_EL_cold, os.path.join(hyd_path, "i_EL_cold.txt"), instance.T)
        export_variable(instance.HDIR_EL, os.path.join(hyd_path, "HDIR_EL.txt"), instance.T)
        export_variable(instance.HCOMP_EL, os.path.join(hyd_path, "HCOMP_EL.txt"), instance.T)
        export_variable(instance.eCOMP, os.path.join(hyd_path, "eCOMP.txt"), instance.T)
        export_variable(instance.HDIR_COMP, os.path.join(hyd_path, "HDIR_COMP.txt"), instance.T)
        export_variable(instance.Hsold, os.path.join(hyd_path, "Hsold.txt"), instance.T)                                                                              
        export_variable(instance.HC_TK, os.path.join(hyd_path, "HC_TK.txt"), instance.T)
        export_variable(instance.LOH, os.path.join(hyd_path, "LOH.txt"), instance.T0)
        export_variable(instance.HDISCH_TK, os.path.join(hyd_path, "HDISCH_TK.txt"), instance.T)
        export_variable(instance.HDIR_TK, os.path.join(hyd_path, "HDIR_TK.txt"), instance.T)
        export_variable(instance.iTK, os.path.join(hyd_path, "iTK.txt"), instance.T)
        export_variable(instance.HFC, os.path.join(hyd_path, "HFC.txt"), instance.T)  
        export_variable(instance.eFC_on, os.path.join(hyd_path, "eFC_on.txt"), instance.T)
        export_variable(instance.eFC_sb, os.path.join(hyd_path, "eFC_sb.txt"), instance.T)
        export_variable(instance.iFC_on, os.path.join(hyd_path, "iFC_on.txt"), instance.T)
        export_variable(instance.iFC_sb, os.path.join(hyd_path, "iFC_sb.txt"), instance.T)
        export_variable(instance.iFC_off, os.path.join(hyd_path, "iFC_off.txt"), instance.T)
        export_variable(instance.i_FC_warm, os.path.join(hyd_path, "i_FC_warm.txt"), instance.T)
        export_variable(instance.i_FC_cold, os.path.join(hyd_path, "i_FC_cold.txt"), instance.T)
        

    # Print header for Scenarios
    with open(os.path.join(project_root, pathmarketres, resfile), "a") as res_log:
        res_log.write("\n###### Printing Scenarios #########\n\n")
    
    # Define the Scenarios results directory
    scenarios_path = os.path.join(project_root, pathmarketres)
    os.makedirs(scenarios_path, exist_ok=True)
    
    # Store Scenarios Data (Scen0)
    scenarios_file = os.path.join(scenarios_path, "scenarios.txt")
    with open(scenarios_file, "w") as f:
        for s in instance.S:
            f.write(f"{s} {value(instance.Prob[s])} ")
            for n in range(1, value(instance.nRV) + 1):
                f.write(f"{value(instance.Scen0[n, s])} ")
            f.write("\n")
    
    # Store Scenario Tree (Clusters)
    tree_file = os.path.join(scenarios_path, "tree.txt")
    with open(tree_file, "w") as f:
        for k in instance.S:
            f.write(f"{k} ")
            for s in instance.SG0:
                if s == 1:
                    x=1
                for i in instance.S0:
                    if i == 1:
                        x=1
                    # Find the minimum representative scenario `m` in cluster `c[s, i]`
                    cluster_members = [m for m in instance.c[s, i] if m == k]
                    if cluster_members:
                        min_representative = min(instance.c[s, i])
                        f.write(f"{min_representative} ")
            f.write("\n")
    
    # Print header for Objective Function
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\n###### Objective Function #########\n\n")
    
    # Define the Objective function results directory
    obj_path = os.path.join(project_root, pathres, "OBJ/")
    os.makedirs(obj_path, exist_ok=True)

    # Compute Objective Function Components
    obj_fun = value(instance.EECSW)
    
    obj_DA_income = sum(value(instance.Prob[s]) * value(instance.lD[t, s]) * 
        (value(instance.eDA_p[t, s]) - value(instance.eDA_m[t, s]))
        for t in instance.T for s in instance.S)
    
    obj_RM_income = sum(value(instance.Prob[s]) * (value(instance.rD[t, s]) + value(instance.rU[t, s])) * value(instance.lR[t, s])
        for t in instance.T for s in instance.S)
    
    obj_IM_income = sum(value(instance.Prob[s]) * sum(value(instance.lI[i, t, s]) * value(instance.eIM[i, t, s]) for i in instance.IMT[t])
        for t in instance.T for s in instance.S)
    
    obj_IB_income = sum(value(instance.Prob[s]) * value(instance.lPIB[t, s]) * value(instance.pIB_p[t, s])
        for t in instance.T for s in instance.S)
    
    obj_BESS_costs = sum(value(instance.Prob[s]) * 
        ((value(instance.dV[t, s]) + value(instance.cV[t, s]))/(2 * value(instance.Emax))) * (value(instance.B_sp_cost) * value(instance.Emax) / value(instance.cyc_max))
        for t in instance.T for s in instance.S)

    if include_h2:
        obj_H2_income = sum(value(instance.Prob[s]) * value(instance.lambda_H) * 
            value(instance.Hsold[t, s]) * value(instance.can_sell_H2)
            for t in instance.T for s in instance.S)    
                                                            
        obj_H2_DEM = sum(value(instance.lambda_H) * value(instance.HDEM[t])
            for t in instance.T)
        
        obj_wat_costs = sum(value(instance.Prob[s]) * value(instance.lambda_wat) * value(instance.sp_wat_EL) *
            value(instance.HEL[t, s])
            for t in instance.T for s in instance.S)

        obj_warm_st_costs = sum(value(instance.Prob[s]) * value(instance.lambda_warm_st) * 
            value(instance.P_EL_nom) * value(instance.i_EL_warm[t, s]) 
            for t in instance.T for s in instance.S)

        obj_cold_st_costs = sum(value(instance.Prob[s]) * value(instance.lambda_cold_st) * 
            value(instance.P_EL_nom) * value(instance.i_EL_cold[t, s]) 
            for t in instance.T for s in instance.S)

        obj_deg_EL_costs = sum(value(instance.Prob[s]) * value(instance.EL_repl_cost) * 
            value(instance.P_EL_nom) / value(instance.EL_lifetime) * value(instance.iEL_on[t, s])
            for t in instance.T for s in instance.S)
        
        obj_warm_st_costs_FC = sum(value(instance.Prob[s]) * value(instance.lambda_warm_st_FC) * 
            value(instance.P_FC_nom) * value(instance.i_FC_warm[t, s]) 
            for t in instance.T for s in instance.S)

        obj_cold_st_costs_FC = sum(value(instance.Prob[s]) * value(instance.lambda_cold_st_FC) * 
            value(instance.P_FC_nom) * value(instance.i_FC_cold[t, s]) 
            for t in instance.T for s in instance.S)
        
        obj_deg_FC_costs = sum(value(instance.Prob[s]) * value(instance.FC_repl_cost) * 
            value(instance.P_FC_nom) / value(instance.FC_lifetime) * value(instance.iFC_on[t, s])
            for t in instance.T for s in instance.S)
        
    
    obj_IB_costs = sum(value(instance.Prob[s]) * value(instance.lNIB[t, s]) * value(instance.pIB_m[t, s])
        for t in instance.T for s in instance.S)
    
    obj_IB_net = obj_IB_income - obj_IB_costs
    
    obj_FD_costs = sum(value(instance.Prob[s]) * value(instance.C_FD) * 
        (value(instance.var_afd_p[t, s]) + value(instance.var_afd_m[t, s]))
        for t in instance.T for s in instance.S)


    instance.obj_fun[probl, sim] = obj_fun
    instance.obj_DA_income[probl, sim] = obj_DA_income
    instance.obj_RM_income[probl, sim] = obj_RM_income
    instance.obj_IM_income[probl, sim] = obj_IM_income
    instance.obj_IB_income[probl, sim] = obj_IB_income
    instance.obj_IB_costs[probl, sim] = obj_IB_costs
    instance.obj_IB_net[probl, sim] = obj_IB_net
    instance.obj_FD_costs[probl, sim] = obj_FD_costs
    instance.obj_BESS_costs[probl, sim] = obj_BESS_costs
    if include_h2:
        instance.obj_wat_costs[probl, sim] = obj_wat_costs
        instance.obj_warm_st_costs[probl, sim] = obj_warm_st_costs
        instance.obj_cold_st_costs[probl, sim] = obj_cold_st_costs
        instance.obj_deg_EL_costs[probl, sim] = obj_deg_EL_costs
        instance.obj_warm_st_costs_FC[probl, sim] = obj_warm_st_costs_FC
        instance.obj_cold_st_costs_FC[probl, sim] = obj_cold_st_costs_FC
        instance.obj_deg_FC_costs[probl, sim] = obj_deg_FC_costs
        instance.obj_H2_income[probl, sim] = obj_H2_income
        instance.obj_H2_DEM[probl, sim] = obj_H2_DEM

    # Store Objective Function Components
    if include_h2:
        obj_components = {
            "obj_fun.txt": obj_fun,
            "obj_DA_income.txt": obj_DA_income,
            "obj_RM_income.txt": obj_RM_income,
            "obj_IM_income.txt": obj_IM_income,
            "obj_IB_income.txt": obj_IB_income,
            "obj_H2_income.txt": obj_H2_income,
            "obj_H2_DEM.txt": obj_H2_DEM,
            "obj_IB_costs.txt": obj_IB_costs,
            "obj_IB_net.txt": obj_IB_net,
            "obj_FD_costs.txt": obj_FD_costs,
            "obj_BESS_costs.txt": obj_BESS_costs,
            "obj_wat_costs.txt": obj_wat_costs,
            "obj_warm_st_costs.txt": obj_warm_st_costs,
            "obj_cold_st_costs.txt": obj_cold_st_costs,
            "obj_deg_EL_costs.txt": obj_deg_EL_costs,
            "obj_warm_st_costs_FC.txt": obj_warm_st_costs_FC,
            "obj_cold_st_costs_FC.txt": obj_cold_st_costs_FC,
            "obj_deg_FC_costs.txt": obj_deg_FC_costs,
        }
    else:
        obj_components = {
            "obj_fun.txt": obj_fun,
            "obj_DA_income.txt": obj_DA_income,
            "obj_RM_income.txt": obj_RM_income,
            "obj_IM_income.txt": obj_IM_income,
            "obj_IB_income.txt": obj_IB_income,
            "obj_IB_costs.txt": obj_IB_costs,
            "obj_IB_net.txt": obj_IB_net,
            "obj_FD_costs.txt": obj_FD_costs,
            "obj_BESS_costs.txt": obj_BESS_costs
        }

    
    for filename, obj_val in obj_components.items():
        with open(os.path.join(obj_path, filename), "w") as f:
            f.write(f"{obj_val}\n")

    # -------------------------------------------------
    # Print Objective Function and its Components to Results Log
    # -------------------------------------------------
    with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
        res_log.write("\n#######################################################\n")
        res_log.write(f"Objective Function and its Components {probl}\n")
    
        res_log.write(f"obj_fun = {value(instance.obj_fun[probl, sim]):6.0f}\n")
        res_log.write(f"obj_DA_income = {value(instance.obj_DA_income[probl, sim]):6.0f}\n")
        res_log.write(f"obj_RM_income = {value(instance.obj_RM_income[probl, sim]):6.0f}\n")
        res_log.write(f"obj_IM_income = {value(instance.obj_IM_income[probl, sim]):6.0f}\n")
        res_log.write(f"obj_IB_income = {value(instance.obj_IB_income[probl, sim]):6.0f}\n")
        res_log.write(f"obj_IB_costs = {value(instance.obj_IB_costs[probl, sim]):6.0f}\n")
        res_log.write(f"obj_IB_net = {value(instance.obj_IB_net[probl, sim]):6.0f}\n")
        res_log.write(f"obj_FD_costs = {value(instance.obj_FD_costs[probl, sim]):6.0f}\n")
        res_log.write(f"obj_BESS_costs = {value(instance.obj_BESS_costs[probl, sim]):6.0f}\n")
        if include_h2:
            res_log.write(f"obj_H2_income = {value(instance.obj_H2_income[probl, sim]):6.0f}\n")
            res_log.write(f"obj_H2_DEM = {value(instance.obj_H2_DEM[probl, sim]):6.0f}\n")
            res_log.write(f"obj_wat_costs = {value(instance.obj_wat_costs[probl, sim]):6.0f}\n")
            res_log.write(f"obj_warm_st_costs = {value(instance.obj_warm_st_costs[probl, sim]):6.0f}\n")
            res_log.write(f"obj_cold_st_costs = {value(instance.obj_cold_st_costs[probl, sim]):6.0f}\n")
            res_log.write(f"obj_deg_EL_costs = {value(instance.obj_deg_EL_costs[probl, sim]):6.0f}\n")
            res_log.write(f"obj_warm_st_costs_FC = {value(instance.obj_warm_st_costs_FC[probl, sim]):6.0f}\n")
            res_log.write(f"obj_cold_st_costs_FC = {value(instance.obj_cold_st_costs_FC[probl, sim]):6.0f}\n")
            res_log.write(f"obj_deg_FC_costs = {value(instance.obj_deg_FC_costs[probl, sim]):6.0f}\n")
        
        res_log.write("#######################################################\n")

    obj_results["obj_fun"][sim] = obj_fun
    obj_results["obj_DA_income"][sim] = obj_DA_income
    obj_results["obj_RM_income"][sim] = obj_RM_income
    obj_results["obj_IM_income"][sim] = obj_IM_income
    obj_results["obj_IB_income"][sim] = obj_IB_income
    obj_results["obj_IB_costs"][sim] = obj_IB_costs
    obj_results["obj_IB_net"][sim] = obj_IB_net
    obj_results["obj_FD_costs"][sim] = obj_FD_costs
    obj_results["obj_BESS_costs"][sim] = obj_BESS_costs
    if include_h2:
        obj_results["obj_H2_income"][sim] = obj_H2_income
        obj_results["obj_H2_DEM"][sim] = obj_H2_DEM
        obj_results["obj_wat_costs"][sim] = obj_wat_costs
        obj_results["obj_warm_st_costs"][sim] = obj_warm_st_costs
        obj_results["obj_cold_st_costs"][sim] = obj_cold_st_costs
        obj_results["obj_deg_EL_costs"][sim] = obj_deg_EL_costs
        obj_results["obj_warm_st_costs_FC"][sim] = obj_warm_st_costs_FC
        obj_results["obj_cold_st_costs_FC"][sim] = obj_cold_st_costs_FC
        obj_results["obj_deg_FC_costs"][sim] = obj_deg_FC_costs
    
    # EX-POST ANALYSIS
    # ------------------------
    # 1) Extract realized branch index
    # ------------------------
    s_or = int(value(instance.sOR))
    print(f"\n→ Ex-post replay on realized scenario branch sOR = {s_or}\n")
    
    # ------------------------
    # 2) Build indices
    # ------------------------
    T  = list(instance.T)
    IM = list(instance.IM)
    IMT = lambda t: list(instance.IMT[t])   # intraday markets active at t
    
    # ------------------------
    # 3) Pull your decisions at (t, sOR)
    # ------------------------
    eDA_p_obs    = {t: value(instance.eDA_p[t,    s_or]) for t in T}
    eDA_m_obs    = {t: value(instance.eDA_m[t,    s_or]) for t in T}
    rU_obs       = {t: value(instance.rU[t,       s_or]) for t in T}
    rD_obs       = {t: value(instance.rD[t,       s_or]) for t in T}
    eIM_obs      = {(i,t): value(instance.eIM[i, t, s_or]) for t in T for i in IMT(t)}
    pIB_p_obs    = {t: value(instance.pIB_p[t,    s_or]) for t in T}
    pIB_m_obs    = {t: value(instance.pIB_m[t,    s_or]) for t in T}
    var_afd_p_obs= {t: value(instance.var_afd_p[t,s_or]) for t in T}
    var_afd_m_obs= {t: value(instance.var_afd_m[t,s_or]) for t in T}
    dV_obs       = {t: value(instance.dV[t,      s_or]) for t in T}
    cV_obs       = {t: value(instance.cV[t,      s_or]) for t in T}
    if include_h2:
        Hsold_obs    = {t: value(instance.Hsold[t,   s_or]) for t in T}
        HDEM         = {t: value(instance.HDEM[t]) for t in T}
        HEL_obs      = {t: value(instance.HEL[t,     s_or]) for t in T}
        i_EL_warm_obs= {t: value(instance.i_EL_warm[t,s_or]) for t in T}
        i_EL_cold_obs= {t: value(instance.i_EL_cold[t,s_or]) for t in T}
        iEL_on_obs   = {t: value(instance.iEL_on[t,  s_or]) for t in T}
        i_FC_warm_obs= {t: value(instance.i_FC_warm[t,s_or]) for t in T}
        i_FC_cold_obs= {t: value(instance.i_FC_cold[t,s_or]) for t in T}
        iFC_on_obs   = {t: value(instance.iFC_on[t,  s_or]) for t in T}

    # ------------------------
    # 4) Pull ex-post data from ScenO
    # ------------------------
    # Helper to read rv→t or market index
    def scenO(rv):
        return value(instance.ScenO[rv])

    # Wind & PV
    pW_obs  = {}
    pPV_obs = {}
    for t in T:
        rv_w = value(instance.fRVSG[value(instance.sgpw[t])])
        rv_p = rv_w + 1
        pW_obs[t]  = min(scenO(rv_w), 1.0) * value(instance.P_W)
        pPV_obs[t] = min(scenO(rv_p), 1.0) * value(instance.P_PV)
    
    # Day-ahead price
    lD_price = {t: scenO(t) for t in T}
    # Reserve market price: assume rv = nT + t
    lR_price = {t: scenO(value(instance.nT) + t) for t in T}
        
    # Imbalance price: rv = fRVSG[nSG] + (t-1)
    imb_off = value(instance.fRVSG[value(instance.nSG)])
    lIB_price = {t: scenO(imb_off + (t-1)) for t in T}
    
    # positive/negative imbalance‐bound price rules
    lPIB_price = {}
    lNIB_price = {}
    for t in T:
        lD = lD_price[t]
        lIB = lIB_price[t]
        if lIB <= 1:
            lPIB_price[t] = min(180.3, lIB * lD)
            lNIB_price[t] =        lD
        else:
            lPIB_price[t] =        lD
            lNIB_price[t] = min(180.3, lIB * lD)
    
    # Intraday prices
    lI_price = {}
    for i in instance.IM:
        # find the RV base for market i
        sg_idx    = value(instance.sgim[i])               # the “sgim[i]” group
        rv_base   = value(instance.fRVSG[sg_idx])         # maps that group → first RV index
        t0        = min(instance.TIM[i])                  # your starting time for this IM
        for t in instance.TIM[i]:
            rv    = rv_base + (t - t0)                    # exactly as in your ec_run.py
            lI_price[i, t] = scenO(rv)

    # 5) & 6) Extract scalar params
        C_FD         = value(instance.C_FD)
        cyc_max        = value(instance.cyc_max)
        B_sp_cost      = value(instance.B_sp_cost)
        Emax           = value(instance.Emax)
        if include_h2:
            lambda_H     = value(instance.lambda_H)
            can_sell_H2  = value(instance.can_sell_H2)
            lambda_wat   = value(instance.lambda_wat)
            sp_wat_EL    = value(instance.sp_wat_EL)
            lambda_warm_EL = value(instance.lambda_warm_st)
            lambda_cold_EL = value(instance.lambda_cold_st)
            P_EL_nom       = value(instance.P_EL_nom)
            EL_repl_cost   = value(instance.EL_repl_cost)
            EL_lifetime    = value(instance.EL_lifetime)
            lambda_warm_FC = value(instance.lambda_warm_st_FC)
            lambda_cold_FC = value(instance.lambda_cold_st_FC)
            P_FC_nom       = value(instance.P_FC_nom)
            FC_repl_cost   = value(instance.FC_repl_cost)
            FC_lifetime    = value(instance.FC_lifetime)
            
       
    # 7) Compute **every** revenue & cost term
    DA_rev           = sum((eDA_p_obs[t] - eDA_m_obs[t]) * lD_price[t]           for t in T)
    RM_rev           = sum((rD_obs[t]  + rU_obs[t]) * lR_price[t]               for t in T)
    ID_rev            = sum(eIM_obs[i,t] * lI_price[i,t]                        for t in T for i in IMT(t))
    IB_rev           = sum(pIB_p_obs[t] * lPIB_price[t]                         for t in T) \
                      - sum(pIB_m_obs[t] * lNIB_price[t]                         for t in T)
    FD_cost          = sum(C_FD * (var_afd_p_obs[t] + var_afd_m_obs[t])         for t in T)
    BESS_deg_cost    = sum((dV_obs[t] + cV_obs[t]) / (2 * Emax) * B_sp_cost * Emax / cyc_max for t in T)
    
    if include_h2:
        H2_rev           = sum(lambda_H * Hsold_obs[t] * can_sell_H2                for t in T)
        H2_DEM           = sum(lambda_H * HDEM[t]                                   for t in T)
        water_cost       = sum(lambda_wat * sp_wat_EL * HEL_obs[t]                  for t in T)
        warm_EL_cost     = sum(lambda_warm_EL * P_EL_nom * i_EL_warm_obs[t]         for t in T)
        cold_EL_cost     = sum(lambda_cold_EL * P_EL_nom * i_EL_cold_obs[t]         for t in T)
        EL_repl_cost_term= sum(EL_repl_cost * P_EL_nom/EL_lifetime * iEL_on_obs[t] for t in T)
        warm_FC_cost     = sum(lambda_warm_FC * P_FC_nom * i_FC_warm_obs[t]         for t in T)
        cold_FC_cost     = sum(lambda_cold_FC * P_FC_nom * i_FC_cold_obs[t]         for t in T)
        FC_repl_cost_term= sum(FC_repl_cost * P_FC_nom/FC_lifetime * iFC_on_obs[t] for t in T)

        ex_post_full = (
            DA_rev + RM_rev + ID_rev + IB_rev + H2_rev + H2_DEM
        - FD_cost - BESS_deg_cost - water_cost
        - warm_EL_cost - cold_EL_cost - EL_repl_cost_term
        - warm_FC_cost - cold_FC_cost - FC_repl_cost_term
        )
    else:
        ex_post_full = (
            DA_rev + RM_rev + ID_rev + IB_rev 
        - FD_cost - BESS_deg_cost
        )
    
    # 8) Print a clean breakdown
    print("===== Ex-Post Profit Breakdown =====")
    print(f" Day-Ahead rev:            {DA_rev:10.2f} €")
    print(f" Reserve market rev:      {RM_rev:10.2f} €")
    print(f" Intraday market rev:     {ID_rev:10.2f} €")
    print(f" Imbalance settlement:    {IB_rev:10.2f} €")
    print(f" Flexible-demand cost:   -{FD_cost:10.2f} €")
    print(f" BESS ageing cost:       -{BESS_deg_cost:10.2f} €")
    if include_h2:
        print(f" H₂ sales revenue:         {H2_rev:10.2f} €")
        print(f" H₂ demand revenue:         {H2_DEM:10.2f} €")
        print(f" Water cost EL:          -{water_cost:10.2f} €")
        print(f" EL warm-start cost:     -{warm_EL_cost:10.2f} €")
        print(f" EL cold-start cost:     -{cold_EL_cost:10.2f} €")
        print(f" EL replacement cost:    -{EL_repl_cost_term:10.2f} €")
        print(f" FC warm-start cost:     -{warm_FC_cost:10.2f} €")
        print(f" FC cold-start cost:     -{cold_FC_cost:10.2f} €")
        print(f" FC replacement cost:    -{FC_repl_cost_term:10.2f} €")
        print("----------------------------------------")
    print(f" Total ex-post profit:    {ex_post_full:10.2f} €\n")
            

# -------------------------------------------------
# Print Objective Function and Components Summary to Console
# -------------------------------------------------
print("############################################################")
print(f"Benefit/costs problem {probl}")

# Print header with all scenario labels
print("           ", end=" ")
for s in SIMS:
    print(f"{s:>6s}", end=" ")
print("\n")

# Print Objective Function Components
def print_obj_component(name, results_dict):
    print(f"{name + ' =':<15}", end=" ")  # Append '=' to the name
    for s in SIMS:
        print(f"{results_dict[name].get(s, 0):6.0f}", end=" ")
    print("\n")

print_obj_component("obj_fun", obj_results)
print_obj_component("obj_DA_income", obj_results)
print_obj_component("obj_RM_income", obj_results)
print_obj_component("obj_IM_income", obj_results)
print_obj_component("obj_IB_income", obj_results)
print_obj_component("obj_IB_costs", obj_results)
print_obj_component("obj_IB_net", obj_results)
print_obj_component("obj_FD_costs", obj_results)
print_obj_component("obj_BESS_costs", obj_results)
if include_h2:
    print_obj_component("obj_H2_income", obj_results)
    print_obj_component("obj_H2_DEM", obj_results)
    print_obj_component("obj_wat_costs", obj_results)
    print_obj_component("obj_warm_st_costs", obj_results)
    print_obj_component("obj_cold_st_costs", obj_results)
    print_obj_component("obj_deg_EL_costs", obj_results)
    print_obj_component("obj_warm_st_costs_FC", obj_results)
    print_obj_component("obj_cold_st_costs_FC", obj_results)
    print_obj_component("obj_deg_FC_costs", obj_results)

print("############################################################")


# ---------------------------------------------------------------------------------
# Print solving times
# ---------------------------------------------------------------------------------
print("#" * 80)
print(f"{' ' * 24} Solve elapsed time {probl} =", end=" ")
for sim in SIMS:
    print(f"{solve_time[probl, sim]:7.1f}", end=" ")
print("\n" + "#" * 80)

# ---------------------------------------------------------------------------------
# Print Objective Function and Components in 'results_log.res'
# ---------------------------------------------------------------------------------
with open(os.path.join(project_root, pathres, resfile), "a") as res_log:
    res_log.write("\n#######################################################\n")
    res_log.write(f"Objective Function and its Components {probl}\n")

    # Retrieve values from obj_results dictionary
    res_log.write(f"obj_fun = {obj_results['obj_fun'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_DA_income = {obj_results['obj_DA_income'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_RM_income = {obj_results['obj_RM_income'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_IM_income = {obj_results['obj_IM_income'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_IB_income = {obj_results['obj_IB_income'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_IB_costs = {obj_results['obj_IB_costs'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_IB_net = {obj_results['obj_IB_net'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_FD_costs = {obj_results['obj_FD_costs'].get(sim, 0):.0f}\n")
    res_log.write(f"obj_BESS_costs = {obj_results['obj_BESS_costs'].get(sim, 0):.0f}\n")
    if include_h2:
        res_log.write(f"obj_H2_income = {obj_results['obj_H2_income'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_H2_DEM = {obj_results['obj_H2_DEM'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_wat_costs = {obj_results['obj_wat_costs'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_warm_st_costs = {obj_results['obj_warm_st_costs'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_cold_st_costs = {obj_results['obj_cold_st_costs'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_deg_EL_costs = {obj_results['obj_deg_EL_costs'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_warm_st_costs_FC = {obj_results['obj_warm_st_costs_FC'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_cold_st_costs_FC = {obj_results['obj_cold_st_costs_FC'].get(sim, 0):.0f}\n")
        res_log.write(f"obj_deg_FC_costs = {obj_results['obj_deg_FC_costs'].get(sim, 0):.0f}\n")
    
    res_log.write("#######################################################\n")

# ---------------------------------------------------------------------------------
# Print Objective Function and Components into profit file (ec_"famscen"_"month".out)
# ---------------------------------------------------------------------------------
# Define the path where summary results are stored
pathtablesres = os.path.join(project_root, "results", famscen, "tables/")
os.makedirs(pathtablesres, exist_ok=True)  # Ensure the directory exists

profit_file = os.path.join(pathtablesres, profitfile[probl])
with open(profit_file, "w") as f:
    f.write(f"     {probl} ")
    f.write(" ".join([f"{sim:6s}" for sim in SIMS]) + "\n")

    f.write("obj_fun ")
    f.write(" ".join([f"{obj_results['obj_fun'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_DA_income ")
    f.write(" ".join([f"{obj_results['obj_DA_income'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_RM_income ")
    f.write(" ".join([f"{obj_results['obj_RM_income'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_IM_income ")
    f.write(" ".join([f"{obj_results['obj_IM_income'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_IB_income ")
    f.write(" ".join([f"{obj_results['obj_IB_income'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_IB_costs ")
    f.write(" ".join([f"{obj_results['obj_IB_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_IB_net ")
    f.write(" ".join([f"{obj_results['obj_IB_net'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_FD_costs ")
    f.write(" ".join([f"{obj_results['obj_FD_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

    f.write("obj_BESS_costs ")
    f.write(" ".join([f"{obj_results['obj_BESS_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")
        
    if include_h2:
        f.write("obj_H2_income ")
        f.write(" ".join([f"{obj_results['obj_H2_income'].get(s, 0):6.0f}" for s in SIMS]) + "\n")
        
        f.write("obj_H2_DEM ")
        f.write(" ".join([f"{obj_results['obj_H2_DEM'].get(s, 0):6.0f}" for s in SIMS]) + "\n")
        
        f.write("obj_wat_costs ")
        f.write(" ".join([f"{obj_results['obj_wat_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

        f.write("obj_warm_st_costs ")
        f.write(" ".join([f"{obj_results['obj_warm_st_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

        f.write("obj_cold_st_costs ")
        f.write(" ".join([f"{obj_results['obj_cold_st_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

        f.write("obj_deg_EL_costs ")
        f.write(" ".join([f"{obj_results['obj_deg_EL_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")
        
        f.write("obj_warm_st_costs_FC ")
        f.write(" ".join([f"{obj_results['obj_warm_st_costs_FC'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

        f.write("obj_cold_st_costs_FC ")
        f.write(" ".join([f"{obj_results['obj_cold_st_costs_FC'].get(s, 0):6.0f}" for s in SIMS]) + "\n")

        f.write("obj_deg_FC_costs ")
        f.write(" ".join([f"{obj_results['obj_deg_FC_costs'].get(s, 0):6.0f}" for s in SIMS]) + "\n")
    
    
# ---------------------------------------------------------------------------------
# Print Summary of Computational Time
# ---------------------------------------------------------------------------------
time_file = os.path.join(pathtablesres, timefile[probl])
with open(time_file, "w") as f:
    f.write(f" {probl} ")
    f.write(" ".join([f"{sim:7s}" for sim in SIMS]) + "\n")
    
    f.write("time ")
    f.write(" ".join([f"{solve_time[probl, s]:7.1f}" for s in SIMS]) + "\n")

# ---------------------------------------------------------------------------------
# Print Number of Scenarios File
# ---------------------------------------------------------------------------------
numscen_file = os.path.join(pathtablesres, numscenfile)
with open(numscen_file, "w") as f:
    f.write(f" {probl} ")
    f.write(" ".join([f"{sim:7s}" for sim in SIMS]) + "\n")

    f.write("num scenarios ")
    f.write(" ".join([f"{n_scenarios[probl, s]:7d}" for s in SIMS]) + "\n")


# ---------------------------------------------------------------------------------
# Generate the .out file (equivalent to AMPL output)
# ---------------------------------------------------------------------------------

out_filename = os.path.join(project_root, "results", famscen, f"ec_{famscen}_summary.out")

with open(out_filename, "w") as out_file:
    # Print and store Objective Function Components
    out_file.write("############################################################\n")
    out_file.write(f"Benefit/costs problem {probl}\n")
    
    # Print header with all scenario labels
    out_file.write("           ")
    for sim in SIMS:
        out_file.write(f"{sim:7s} ")
    out_file.write("\n")

    # Function to write objective function components to file
    def write_obj_component(name, key):
        out_file.write(f"{name:<15}")
        for sim in SIMS:
            out_file.write(f"{obj_results[key].get(sim, 0):6.0f} ")
        out_file.write("\n")

    # Write each objective function component
    write_obj_component("obj_fun", "obj_fun")
    write_obj_component("obj_DA_income", "obj_DA_income")
    write_obj_component("obj_RM_income", "obj_RM_income")
    write_obj_component("obj_IM_income", "obj_IM_income")
    write_obj_component("obj_IB_income", "obj_IB_income")
    write_obj_component("obj_IB_costs", "obj_IB_costs")
    write_obj_component("obj_IB_net", "obj_IB_net")
    write_obj_component("obj_FD_costs", "obj_FD_costs")
    write_obj_component("obj_BESS_costs", "obj_BESS_costs")
    if include_h2:
        write_obj_component("obj_H2_income", "obj_H2_income")
        write_obj_component("obj_H2_DEM", "obj_H2_DEM")
        write_obj_component("obj_wat_costs", "obj_wat_costs")
        write_obj_component("obj_warm_st_costs", "obj_warm_st_costs")
        write_obj_component("obj_cold_st_costs", "obj_cold_st_costs")
        write_obj_component("obj_deg_EL_costs", "obj_deg_EL_costs")
        write_obj_component("obj_warm_st_costs_FC", "obj_warm_st_costs_FC")
        write_obj_component("obj_cold_st_costs_FC", "obj_cold_st_costs_FC")
        write_obj_component("obj_deg_FC_costs", "obj_deg_FC_costs")

    out_file.write("############################################################\n")

    # Solve elapsed times
    out_file.write("#" * 80 + "\n")
    out_file.write(f"{' ' * 24} Solve elapsed time {probl} = ")
    for sim in SIMS:
        out_file.write(f"{solve_time[probl, sim]:7.1f} ")
    out_file.write("\n" + "#" * 80 + "\n")

    # Number of scenarios per simulation
    out_file.write(f"\nNumber of Scenarios ({probl})\n")
    out_file.write("           ")
    for sim in SIMS:
        out_file.write(f"{sim:7s} ")
    out_file.write("\nnum scenarios ")
    for sim in SIMS:
        out_file.write(f"{n_scenarios[probl, sim]:7d} ")
    out_file.write("\n")

    out_file.write("\nEND\n")

print(f"\nSummary .out file saved to: {out_filename}")

print("END")