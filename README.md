# SECOEM: Energy Community Optimization with Pyomo

## Table of Contents
1. [Introduction](#introduction)
2. [Setting Up the Environment](#setting-up-the-environment)
3. [Configuration](#configuration)
4. [Running the Simulation](#running-the-simulation)
5. [Output and Results](#output-and-results)
6. [Repository Structure](#repository-structure)
7. [Notes](#notes)

---

## Introduction

**SECOEM** is an optimization model for an energy community interacting with the electricity market to maximize profits. The model is implemented using the **Pyomo** library.
The energy community consists of:
- **Flexible Demand** (implicit modeling)
- **Wind Farm**
- **Solar Farm**
- **Battery Energy Storage System (BESS)**
- **Hydrogen Chain** (optional): electrolyzer, hydrogen storage, fuel cell, and hydrogen demand

The problem is formulated as a **multi-stage stochastic programming model** for optimal multi-market participation under price and variable renewable uncertainty. It considers internal electricity demand, and hydrogen demand if the hydrogen chain is activated.

---

## Setting Up the Environment

This project requires **Python 3.11+**.

### 1. Clone the Repository
```sh
git clone https://github.com/mmobec/secoem.git
cd secoem
```
### 2. Virtual Environment
It is recommended to create a virtual environment for this repository to avoid version conflicts. A virtual environment can be created with `venv`
```sh
python -m venv .venv
```
where `.venv` is the name of the environment. Once created, it can be activated on Linux and Mac with
```sh
source .venv/bin/activate
```
and on Windows with
```sh
.venv\Scripts\activate
```

### 3. Install Dependencies
We recommend installation of all required packages with `pip`. The instruction 
```sh
pip install .
```
automatically installs all required packages in `pyproject.toml`:

More information:
[Python `venv` documentation](https://docs.python.org/3/library/venv.html)


---

## Configuration

Before running the simulation, you must configure the `config.yaml` file located in the `codes/` directory. This file controls all key parameters of the model:

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
famscen: "FTC_202407_202412_c92_sc100_DA"
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

---

## Scenarios

Put the scenario files in pyomo format into `/scenarios`. The naming format is important: scenario files should follow the format `famscen-scenario_number.dat`. For example for `famscen FTC_10_2-24`, the files should be named `FTC_10_2023_12-001.dat` etc..

---

## Running the Code

Navigate to the `codes/` directory:

```sh
cd ../codes
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
- Load the scenario data from `scenarios/` and the energy community data from `data\`
- Create optimal bids for the EC
- Store results in the `results/` directory

## Example

The repository contains a ready-to-run example that requires no additional data download. It is configured via the default `config.yaml` and uses the scenario family `FTC_202407_202412_c92_sc100_DA`.

### Energy Community Assets

| Asset | Parameter | Value |
|---|---|---|
| BESS | Energy capacity  | 30 MWh |
| BESS | Max charge/discharge rate  | proportional (see `ec_BESS.dat`) |
| Wind farm | Nameplate capacity | 20 MW | (see `ec_wind.dat`)
| Solar PV | Nameplate capacity | 15 MW | (see `ec_wind.dat`)
| Flexible demand | Profile | Hourly electrical demand (see `data/demand/`) |

All parameters can be adjusted in their corresponding files.

The scenario tree is a 100-scenario tree for each day.

---

## Output and Results

- The results of the optimization will be stored in the `results/` directory.
- The output includes scheduled energy production, consumption, and trading strategies.

---

## Repository Structure

### 1. Data Files

Data is divided into two directories. The directory `data/` contains all deterministic parameters and the directory `scenarios/` contains all uncertain parameters:

**Electricity:**

a. `data/ec_BESS.dat` —  data file containing the values of the battery's parameters.

b. `data/demand/` — Directory containing the electrical demand profiles.

c. `data/ec_wind.dat` —  data file containing the values of the wind farm and solar PV parameters.

d. `data/market.dat` —  data file containing the market parameters.

**Hydrogen:**

e. `data/ec_HYD.dat` —  data file containing all hydrogen chain parameters (electrolyzer, storage, etc.).

f. `data/demand_h2/` — Directory containing hydrogen demand profiles, analogous to `data/demand/` for electrical demand.

**Scenarios:**

g. `scenarios/famscen/famscen-SIM.dat` —  data file containing the values of all scenarios (electricity market prices, wind and PV generation). It also contains the cluster structure to represent the scenario tree.


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

An updated mathematical formulation in `LaTeX` of the optimization models is maintained in the `model_formulation/` directory


---

## Notes

- If you re-run the simulation, results will be overwritten.
- The `results/` folder is ignored in Git to keep the repository clean.
- Make sure to update `project_root` in `config.yaml` to match the absolute path on your local machine.
- When `include_h2: false`, the `hydrogen_datfile` and `pathdem_h2` parameters in `config.yaml` are ignored.

---

### License

This project is licensed under the GNU License - see the [LICENSE](LICENSE) file for details.

### Contact

For questions or contributions, please open an issue or contact the repository maintainers.
