# SECOEM: Stochastic Energy Community Optimization in Energy Markets with Pyomo

## Table of Contents
1. [Introduction](#introduction)
2. [Setting Up the Environment](#setting-up-the-environment)
3. [Configuration](#configuration)
4. [Running the Models](#running-the-models)
5. [Output and Results](#output-and-results)
6. [Examples](#examples)
7. [Repository Structure](#repository-structure)
8. [Notes](#notes)

---

## Introduction

**SECOEM** is an optimization model for an energy community participating in electricity markets to satisfy its demand at the minimum cost and make the most of excess variable renewable generation. The model is implemented using the **Pyomo** library.
The energy community consists of:
- **Flexible Demand** (implicit modeling)
- **Wind Farm**
- **Solar Farm**
- **Battery Energy Storage System (BESS)**
- **Hydrogen Chain** (optional): electrolyzer, hydrogen storage, fuel cell, and hydrogen demand

The problem is formulated as a **multi-stage stochastic programming model** for optimal multi-market participation under price and variable renewable uncertainty. It considers internal electricity demand, and hydrogen demand if the hydrogen chain is activated.

The repository includes two ready-to-run examples that require no additional data download (see [Examples](#examples)).

---

## Setting Up the Environment

This project requires **Python 3.11+**.

### 1. Clone the Repository
```sh
git clone https://github.com/mmobec/secoem.git
cd secoem
```

### 2. Create and Activate a Virtual Environment

It is recommended to create a virtual environment to avoid version conflicts. Create one with:
```sh
python -m venv .venv
```

Then activate it — on **Linux/Mac**:
```sh
source .venv/bin/activate
```
On **Windows**:
```sh
.venv\Scripts\activate
```

> More information: [Python `venv` documentation](https://docs.python.org/3/library/venv.html)

### 3. Install Dependencies

With the virtual environment active, install all required packages from the root of the repository:
```sh
pip install .
```
This automatically installs all packages listed in `pyproject.toml`.

---

## Configuration

Before running the model, you must configure the `config.yaml` file located in the `codes/` directory. This file controls all key parameters of the model:

```yaml
# Data file names
BESS_datfile: "ec_BESS.dat"
wind_datfile: "ec_wind.dat"
market_datfile: "market.dat"
hydrogen_datfile: "ec_HYD.dat"

# Run mode
MODE: 'multiscen'

# Problem definition
PROB: ["ec"]
probl: 'ec'
famscen: "FTC_2024_10"
include_h2: true
n_days: 1
project_root: "~/secoem"

# Data paths
pathdem: "data/demand/"
pathdem_h2: "data/demand_h2/"

# Output files
resfile: "results_log.res"
timefileFull: "time.txt"
numscenfile: "numscen.txt"
```

### Key parameters to adjust:

| Parameter | Description |
|-----------|-------------|
| `famscen` | Name of the scenario family folder inside `scenarios/` |
| `n_days` | Number of days to simulate |
| `project_root` | Absolute path to the root of the repository on your machine |
| `include_h2` | Set to `true` to include the hydrogen chain, `false` to run electricity-only model |
| `MODE` | Run mode — use `'multiscen'` for stochastic multi-scenario optimization |


### Scenarios

The scenario files in Pyomo format must be placed in the `/scenarios` directory. 

The naming format is important: scenario files should follow the format `famscen-scenario_number.dat`. For example, for the family of scenarios `FTC_10_2024` (`famscen: FTC_10_2024`), the scenario files should be named `FTC_10_2024-001.dat`, `FTC_10_2024-002.dat`, etc.

---

## Running the Models

Make sure you have activated your virtual environment and updated `project_root` in `config.yaml` before executing.

Navigate to the `codes/` directory:
```sh
cd codes
```

Run the optimization model:
```sh
python ec_run.py
```

`ec_run.py` reads `config.yaml` and automatically selects the appropriate model:
- `include_h2: false` → runs `codes/models/ec_model.py` (electricity only)
- `include_h2: true` → runs `codes/models/ec_hydrogen_model.py` (electricity + hydrogen chain)

This will:
- Load the configuration from `config.yaml`
- Load the scenario data from `scenarios/` and the energy community data from `data/`
- Create optimal bids for the EC
- Store results in the `results/` directory

## Output and Results

- The results of the optimization will be stored in the `results/` directory.
- The output includes scheduled energy production, consumption, and trading strategies.


---

## Examples

The repository contains two ready-to-run examples that require no additional data download. They both contain the following assets:

### Energy Community Assets

| Asset           | Parameter                  | Description                                      | Value         |
|------------------|----------------------------|--------------------------------------------------|---------------|
| BESS            | Emax           | Maximum energy storage capacity                 | 30 MWh        |
| BESS            | Dmax  | Maximum rate of charge and discharge (proportional) | See `ec_BESS.dat` |
| Wind farm       | Pavg         | Maximum power generation capacity               | 20 MW         |
| Solar PV        | Pavg_PV         | Maximum power generation capacity               | 15 MW         |
| Flexible demand | profile                    | Hourly electrical demand profile                | See `data/demand/` |

All parameters can be adjusted in their corresponding files (`data/ec_BESS.dat`, `data/ec_wind.dat`, `data/demand`).

Should the hydrogen chain be included using `include_h2 = true`, the following key hydrogen chain parameters are used, which can be modified in `data/ec_HYD.dat`:


| Component              | Parameter                  | Description                                      | Value         |
|------------------------|----------------------------|--------------------------------------------------|---------------|
| **Hydrogen Market**    | `lambda_H`                | Hydrogen cost [€/kg]                            | 3             |
|                        | `lambda_wat`              | Water cost [€/L]                                | 0.004         |
| **Electrolyzer**       | `P_EL_nom`                | Nominal power [MW]                              | 10            |
|                        | `eta_EL`                  | Efficiency [MWh/kg]                             | 0.05          |
|                        | `sp_wat_EL`               | Specific water consumption [L/kg H2]            | 15            |
|                        | `EL_lifetime`             | Lifetime [h]                                    | 80,000        |
|                        | `EL_repl_cost`            | Replacement cost [€/MW]                         | 1,000,000     |
| **Compressor**         | `spec_COMP`               | Specific consumption [MWh/kg]                   | 0.0035        |
|                        | `P_COMP_nom`              | Nominal power [MW]                              | 0.7           |
| **Storage Tank**       | `H_tank_cap`              | Tank capacity [kg]                              | 750           |
|                        | `P_tank`                  | Charge/discharge power [kg/h]                   | 300           |
|                        | `eta_tank`                | Round trip efficiency                           | 0.99          |
| **Fuel Cell**          | `P_FC_nom`                | Nominal power [MW]                              | 6             |
|                        | `eta_FC`                  | Efficiency [kg/MWh]                             | 60            |
|                        | `FC_lifetime`             | Lifetime [h]                                    | 40,000        |
|                        | `FC_repl_cost`            | Replacement cost [€/MW]                         | 900,000       |


### Example 1: `FTC_2024_10`

Example 1 is configured via the default `config.yaml` and uses the scenario family `FTC_2024_10`.

To run this example, once you have [set up the environment](#setting-up-the-environment), do:

#### 1. Update the Project Path

Open `codes/config.yaml` and set `project_root` to the **absolute path** of the repository on your machine:
```yaml
project_root: "/your/absolute/path/to/secoem"
```
> This step is required for the model to correctly locate data and scenario files. The default value will not work on your local machine.

#### 2. Run the Example

Navigate to the `codes/` directory and execute the model:
```sh
cd codes
python ec_run.py
```

After execution, the results will be stored in the `results/FTC_2024_10` directory.


### Example 2: `FTC_202407_202412_c93_sc100`

This is an example with 100 scenarios and uses the scenario family `FTC_202407_202412_c92_sc100`. Running this example is significantly more computationally heavy.

To run it, the user needs to change the `famscen` parameter in `codes/config.yaml` to `FTC_202407_202412_c92_sc100`:
```yaml
famscen: "FTC_202407_202412_c92_sc100"
```

and follow the same steps than in [Example 1](#example-1-ftc_2024_10).

---

## Repository Structure

### 1. Data Files

Data is divided into two directories. The directory `data/` contains all deterministic parameters and the directory `scenarios/` contains all uncertain parameters:

**Electricity:**

a. `data/ec_BESS.dat` — data file containing the values of the battery's parameters.

b. `data/demand/` — Directory containing the electrical demand profiles.

c. `data/ec_wind.dat` — data file containing the values of the wind farm and solar PV parameters.

d. `data/market.dat` — data file containing the market parameters.

**Hydrogen:**

e. `data/ec_HYD.dat` — data file containing all hydrogen chain parameters (electrolyzer, storage, etc.).

f. `data/demand_h2/` — Directory containing hydrogen demand profiles, analogous to `data/demand/` for electrical demand.

**Scenarios:**

g. `scenarios/famscen/famscen-SIM.dat` — data file containing the values of all scenarios (electricity market prices, wind and PV generation). It also contains the cluster structure to represent the scenario tree.

### 2. Code Files

The code files are in the directory `codes/`:

a. `codes/ec_run.py` — Controls the execution of the model. Reads `config.yaml`, selects the appropriate model based on the `include_h2` flag, loads data from `data/` and `scenarios/`, executes the optimization, and stores results in `results/`.

b. `codes/config.yaml` — All user-configurable parameters. See the [Configuration](#configuration) section.

c. `codes/models/ec_model.py` — Pyomo Abstract Model for the electricity-only energy community. Follows the mathematical formulation in `model_formulation/ec_model_formulation.pdf`.

d. `codes/models/ec_hydrogen_model.py` — Extended Pyomo Abstract Model that includes the hydrogen chain (electrolyzer, hydrogen storage, hydrogen demand) in addition to the electricity components.

### 3. Results Files

The directory `results/` contains the results files of the days for which the model has been executed.

They are indexed by scenario family. This means that if the code has been executed for the scenario family `famscen`, the results will be stored in `results/famscen/`.

### 4. Mathematical Formulation Files

An updated mathematical formulation in LaTeX of the optimization models is maintained in the `model_formulation/` directory.

---

## Notes

- If you re-run the simulation, results will be overwritten.
- The `results/` folder is ignored in Git to keep the repository clean.
- Make sure to update `project_root` in `config.yaml` to match the absolute path on your local machine.
- When `include_h2: false`, the `hydrogen_datfile` and `pathdem_h2` parameters in `config.yaml` are ignored.

---

### License

This project is licensed under the GNU License — see the [LICENSE](LICENSE) file for details.

### Contact

For questions or contributions, please open an issue or contact the repository maintainers.
