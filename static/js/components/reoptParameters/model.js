export { REoptParametersModel, REoptParameters, REoptParameter, REoptIntParameter, REoptFloatParameter, REoptStringParameter, REoptJsonObjectParameter, REoptBooleanParameter };
import { Observable } from '../observable.js';

/**
 * - A model is useful because it can wrap multiple instances of the underlying model
 *  - E.g. if I didn't have this class, I would just put REoptParameter instances into an object, which is not good software design
 */
class REoptParametersModel {
    
    #reoptParametersInstances;

    constructor() {
        this.#reoptParametersInstances = {};
    }

    /**
     * @returns {Array}
     */
    get reoptParametersInstances() {
        return this.#reoptParametersInstances;
    }

    set reoptParametersInstances(reoptParametersInstances) {
        throw Error('read-only accessor descriptor');
    }

    /**
     * @param {string} reoptParametersInstanceName - The name of a microgrid
     * @returns {undefined}
     */
    addReoptParametersInstance(reoptParametersInstanceName) {
        if (typeof reoptParametersInstanceName !== 'string') {
            throw TypeError('The "reoptParametersInstanceName" argument must be typeof "string".');
        }
        if (Object.hasOwn(this.#reoptParametersInstances, reoptParametersInstanceName)) {
            throw Error('The "reoptParametersInstanceName" argument already exists.');
        }
        this.#reoptParametersInstances[reoptParametersInstanceName] = new REoptParameters();
    }

    /**
     * @param {string} reoptParametersInstanceName - The name of a microgrid
     * @returns {REoptParameters}
     */
    getReoptParametersInstance(reoptParametersInstanceName) {
        if (typeof reoptParametersInstanceName !== 'string') {
            throw TypeError('The "name" argument must be typeof "string".');
        }
        if (!Object.hasOwn(this.#reoptParametersInstances, reoptParametersInstanceName)) {
            throw Error(`The REoptParameters instance called "${reoptParametersInstanceName}" does not exist`);
        }
        return this.#reoptParametersInstances[reoptParametersInstanceName];
    }

    /**
     * - I still want to change the schema on the back-end so that I can get rid of this alias property, but this is fine for now
     */
    getExportData() {
        const parameter_overrides = {};
        for (const [microgridName, reoptParameters] of Object.entries(this.#reoptParametersInstances)) {
            parameter_overrides[microgridName] = {
                reopt_inputs: {}
            };
            for(const reoptParameter of reoptParameters.reoptParameters) {
                if (reoptParameter.isSet()) {
                    if (['MicrogridUp:singlePhaseRelayCost', 'MicrogridUp:threePhaseRelayCost'].includes(reoptParameter.parameterName)) {
                        parameter_overrides[microgridName][reoptParameter.alias] = reoptParameter.value
                    } else {
                        parameter_overrides[microgridName]['reopt_inputs'][reoptParameter.alias] = reoptParameter.value;
                    }
                }
            }
        }
        return parameter_overrides;
    }

    /**
     * @param {string} reoptParametersInstanceName - The name of a microgrid
     * @returns {undefined}
     */
    hasReoptParametersInstance(reoptParametersInstanceName) {
        if (typeof reoptParametersInstanceName !== 'string') {
            throw TypeError('The "reoptParametersInstanceName" argument must be typeof "string".');
        }
        if (Object.hasOwn(this.#reoptParametersInstances, reoptParametersInstanceName)) {
            return true;
        }
        return false;
    }

    /**
     * @param {string} reoptParametersInstanceName - The name of a microgrid
     * @returns {undefined}
     */
    removeReoptParametersInstance(reoptParametersInstanceName) {
        if (typeof reoptParametersInstanceName !== 'string') {
            throw TypeError('The "reoptParametersInstanceName" argument must be typeof "string".');
        }
        if (!Object.hasOwn(this.#reoptParametersInstances, reoptParametersInstanceName)) {
            throw Error('The "reoptParametersInstanceName" argument does not exist.');
        }
        delete this.#reoptParametersInstances[reoptParametersInstanceName];
    }

    /**
     * - Set the model back to it's initial state
     */
    reset() {
        for (const reoptParametersInstance of Object.values(this.#reoptParametersInstances)) {
            reoptParametersInstance.removeObservers();
            this.#reoptParametersInstances = {};
        }
    }
}

class REoptParameters extends Observable {
    #reoptParameters;

    constructor() {
        super();
        // - These parameters match the casing of REopt, which uses both PascalCase and snake_case
        this.#reoptParameters = {
            ElectricLoad: {
                year: new REoptIntParameter(
                    'Year',
                    'ElectricLoad:year',
                    'year',
                    'Specify the year to which the load shape values correspond.',
                    2100,
                    1900)
            },
            ElectricStorage: {
                battery_replacement_year:   new REoptIntParameter(
                                                'Battery Capacity Replacement (years)',
                                                'ElectricStorage:battery_replacement_year',
                                                'batteryCapacityReplaceYear',
                                                'Specify a year in which the battery cells will be replaced at the cost specified in Battery Replacement Capacity Cost. Input is an integer less than or equal to the project period in years.',
                                                100,
                                                0),
                installed_cost_per_kw:      new REoptFloatParameter(
                                                'Battery Power Cost ($/kW-AC)',
                                                'ElectricStorage:installed_cost_per_kw',
                                                'batteryPowerCost',
                                                'Specify the cost in $/kW.',
                                                1.0e9,
                                                0),
                installed_cost_per_kwh:     new REoptFloatParameter(
                                                'Battery Capacity Cost ($/kWh-AC)',
                                                'ElectricStorage:installed_cost_per_kwh',
                                                'batteryCapacityCost',
                                                'Specify the cost in $/kWh.',
                                                1.0e9,
                                                0),
                inverter_replacement_year:  new REoptIntParameter(
                                                'Battery Power Replacement (years)',
                                                'ElectricStorage:inverter_replacement_year',
                                                'batteryPowerReplaceYear',
                                                'Specify a year in which the battery power will be replaced at the cost specified in Battery Replacement Power Cost. Input is an integer less than or equal to the project period in years.',
                                                100,
                                                0),
                macrs_option_years:         new REoptIntParameter(
                                                'Battery MACRS Years',
                                                'ElectricStorage:macrs_option_years',
                                                'batteryMacrsOptionYears',
                                                'MACRS schedule for financial analysis. Possible inputs are 0, 5 and 7 years. Set to zero to disable accelerated depreciation accounting for solar.',
                                                100,
                                                0),
                max_kw:                     new REoptFloatParameter(
                                                'Battery Power Max (kW-AC)',
                                                'ElectricStorage:max_kw',
                                                'batteryPowerMax',
                                                'Specify the maximum desired battery power in kW.',
                                                1.0e4,
                                                0),
                max_kwh:                    new REoptFloatParameter(
                                                'Battery Capacity Max (kWh-AC)',
                                                'ElectricStorage:max_kwh',
                                                'batteryCapacityMax',
                                                'Specify the maximum desired battery capacity in kWh.',
                                                1.0e6,
                                                0),
                soc_min_fraction:           new REoptFloatParameter(
                                                'Battery Min State of Charge (0–1)',
                                                'ElectricStorage:soc_min_fraction',
                                                'batterySocMinFraction',
                                                'Minimum state of charge (SOC) that REopt maintains in the battery at all times during an outage, expressed as a fraction (0–1). The default of 0.2 reflects real-world depth-of-discharge limits for lithium-ion batteries, which degrade faster with deep cycling. Set to 0.0 for storage technologies that support full discharge, such as pumped hydro, compressed air energy storage (CAES), or iron-air batteries.',
                                                1.0,
                                                0),
                mgu_enabled:                new REoptBooleanParameter(
                                                'Batteries',
                                                'ElectricStorage:mgu_enabled',
                                                'battery',
                                                'Specify whether batteries should be a part of the microgrid design.'),
                min_kw:                     new REoptFloatParameter(
                                                'Battery Power Min (kW-AC)',
                                                'ElectricStorage:min_kw',
                                                'batteryPowerMin',
                                                'Specify the minimum desired battery power in kW.',
                                                1.0e4,
                                                0),
                min_kwh:                    new REoptFloatParameter(
                                                'Battery Capacity Min (kWh-AC)',
                                                'ElectricStorage:min_kwh',
                                                'batteryCapacityMin',
                                                'Specify the minimum desired battery capacity in kWh.',
                                                1.0e6,
                                                0),
                total_itc_pct:              new REoptFloatParameter(
                                                'Battery ITC (% as decimal)',
                                                'ElectricStorage:total_itc_pct',
                                                'batteryItcPercent',
                                                'Please enter a number 0-1 for the battery investment tax credit. Format 0.XX',
                                                1,
                                                0),
                replace_cost_per_kw:        new REoptFloatParameter(
                                                'Battery Replacement Power Cost ($/kW-AC)',
                                                'ElectricStorage:replace_cost_per_kw',
                                                'batteryPowerCostReplace',
                                                'Specify the cost of replacing the battery inverter at the specified year in $/kW.',
                                                1.0e9,
                                                0),
                replace_cost_per_kwh:       new REoptFloatParameter(
                                                'Battery Replacement Capacity Cost ($/kWh-AC)',
                                                'ElectricStorage:replace_cost_per_kwh',
                                                'batteryCapacityCostReplace',
                                                'Specify the cost of replacing the battery capacity at the specified year in $/kWh.',
                                                1.0e9,
                                                0)
            },
            ElectricTariff: {
                blended_annual_energy_rate: new REoptFloatParameter(
                                                'Energy Cost ($/kWh)',
                                                'ElectricTariff:blended_annual_energy_rate',
                                                'energyCost',
                                                'Specify the energy cost. Format 0.XX',
                                                1.0e9,
                                                0),
                blended_annual_demand_rate: new REoptFloatParameter(
                                                'Demand Cost ($/kW)',
                                                'ElectricTariff:blended_annual_demand_rate',
                                                'demandCost',
                                                'Specify the demand cost in $/kW. Format 0.XX',
                                                1.0e9,
                                                0),
                //urdb_label:                 new REoptStringParameter(
                //                                'URDB Label',
                //                                'ElectricTariff:urdb_label',
                //                                'urdbLabel',
                //                                'Input the string found at the end of the URDB Rate URL. For example, <a href="https://openei.org/apps/IURDB/rate/view/5b75cfe95457a3454faf0aea">this rate data entry</a> would be "5b75cfe95457a3454faf0aea"',
                //                                /.+/),
                //mgu_urdb_label_enabled:     new REoptBooleanParameter(
                //                                'Use URDB Rate?',
                //                                'ElectricTariff:mgu_urdb_label_enabled',
                //                                'urdbLabelSwitch',
                //                                'Utilizing a rate from the Utility Rate Database overrides Cost of Energy and Cost of Demand rates above. See <a href="https://openei.org/services/doc/rest/util_rates/">OpenEI</a> for more information.'),
                wholesale_rate:             new REoptFloatParameter(
                                                'Exported Power Cost ($/kWh)',
                                                'ElectricTariff:wholesale_rate',
                                                'wholesaleCost',
                                                'Specify the price the grid operator pays for power exported by the microgrid, i.e. generation beyond the site load. It applies whether the tariff comes from Energy Cost and Demand Cost or from a Custom URDB Rate, and it is ignored when "DG Can Export" is No, which curtails the excess generation instead. A value of 0 leaves export allowed but unpaid, so the optimizer will not size generation for it. Format 0.XX',
                                                1.0e9,
                                                0),
                urdb_response:              new REoptJsonObjectParameter(
                                                'Custom URDB Rate (JSON format)',
                                                'ElectricTariff:urdb_response',
                                                'urdbResponse',
                                                'Optional. Paste a utility rate in the <a href="https://openei.org/services/doc/rest/util_rates/?version=7"><u>URDB JSON format</u></a> to model a rate that is not in the URDB. When this field is set, it is sent to REopt as a urdb_response and takes precedence over Energy Cost and Demand Cost. The easiest way to generate a custom rate is to go to the <a href="https://reopt.nlr.gov/tool/custom_tariffs"><u>REopt tariff builder</u></a>, build the rate, and download the JSON file. The keys energyratestructure, energyweekdayschedule, and energyweekendschedule are required. Demand charges, tiers, and fixed charges are optional. Rate periods are zero-indexed. See the <a href="https://natlabrockies.github.io/REopt.jl/dev/reopt/inputs/#ElectricTariff"><u>REopt.jl ElectricTariff inputs</u></a> for the full list of recognized keys.',
                                                ['energyratestructure', 'energyweekdayschedule', 'energyweekendschedule'],
                                                '{"energyratestructure": [[{"rate": 0.06}], [{"rate": 0.15}]], "energyweekdayschedule": [[0, 0, ...]], "energyweekendschedule": [[0, 0, ...]]}'),
            },
            Financial: {
                analysis_years:             new REoptIntParameter(
                                                'Analysis Period (years)',
                                                'Financial:analysis_years',
                                                'analysisYears',
                                                'Please enter a number 2-75 to specify the length of financial analysis in years.',
                                                75,
                                                2),
                offtaker_discount_pct:      new REoptFloatParameter(
                                                'Discount Rate (% per year)',
                                                'Financial:offtaker_discount_pct',
                                                'discountRate',
                                                'Please enter a number 0-1 for the rate used to discount future cash flows in a net present value analysis. In single ownership model the offtaker is also the generation owner. Format 0.XXX',
                                                1,
                                                0),
                om_cost_escalation_pct:     new REoptFloatParameter(
                                                'O+M Escalation (% per year)',
                                                'Financial:om_cost_escalation_pct',
                                                'omCostEscalator',
                                                'Please enter a number 0-1 for the Annual nominal O&M cost escalation rate. Format 0.XXX',
                                                1,
                                                0),
                value_of_lost_load_per_kwh: new REoptFloatParameter(
                                                'Value of Lost Load ($/kWh)',
                                                'Financial:value_of_lost_load_per_kwh',
                                                'value_of_lost_load',
                                                'Specify the value of lost load during a power outage in $/kWh.',
                                                1.0e9,
                                                0),
            },
            Generator: {
                emissions_factor_lb_CO2_per_gal:    new REoptFloatParameter(
                                                        'Genset Emissions Factor (lb CO2/gal)',
                                                        'Generator:emissions_factor_lb_CO2_per_gal',
                                                        'dieselCO2Factor',
                                                        'Specify fossil emissions factor in pounds of carbon dioxide per gallon. Default 22.4 is for diesel. Natural gas can be modeled using 24.1',
                                                        1.0e9,
                                                        0),
                only_runs_during_grid_outage:       new REoptBooleanParameter(
                                                        'Genset only runs during outage?',
                                                        'Generator:only_runs_during_grid_outage',
                                                        'dieselOnlyRunsDuringOutage',
                                                        '"No" signifies that fossil generator is enabled to run at any point in the year.'),
                fuel_avail_gal:                     new REoptFloatParameter(
                                                        'Fuel Available (Gal)',
                                                        'Generator:fuel_avail_gal',
                                                        'fuelAvailable',
                                                        'Specify the amount of fuel available for all new and pre-existing generators in gallons.',
                                                        1.0e9,
                                                        0),
                fuel_cost_per_gallon:               new REoptFloatParameter(
                                                        'Fuel Cost (diesel gal equiv)',
                                                        'Generator:fuel_cost_per_gallon',
                                                        'dieselFuelCostGal',
                                                        'Specify cost of fuel in $ per gallon. To convert $/MMBTU of Natural gas to gallons of diesel, divide $/MMBTU market rate by 4.85 to account for 50% lower efficiency of natural gas reciprocating engines and lower fuel density as compared to diesel. Format X.XX',
                                                        1.0e9,
                                                        0),
                installed_cost_per_kw:              new REoptFloatParameter(
                                                        'Genset Cost ($/kW)',
                                                        'Generator:installed_cost_per_kw',
                                                        'dieselGenCost',
                                                        'Specify the cost in $/kWh.',
                                                        1.0e9,
                                                        0),
                macrs_option_years:                 new REoptIntParameter(
                                                        'Fossil MACRS Years',
                                                        'Generator:macrs_option_years',
                                                        'dieselMacrsOptionYears',
                                                        'MACRS schedule for financial analysis. Possible inputs are 0, 15 and 20 years. Set to zero to disable accelerated depreciation accounting for solar.',
                                                        100,
                                                        0),
                max_kw:                             new REoptFloatParameter(
                                                        'Genset Max (kW)',
                                                        'Generator:max_kw',
                                                        'dieselMax',
                                                        'Specify max fossil generation in kW. Only specify if needed, as the optimization runs best if left unedited.',
                                                        1.0e6,
                                                        0),
                mgu_enabled:                        new REoptBooleanParameter(
                                                        'Fossil',
                                                        'Generator:mgu_enabled',
                                                        'fossil',
                                                        'Specify whether fossil generators should be a part of the microgrid design.'),
                min_kw:                             new REoptFloatParameter(
                                                        'Genset Min (kW)',
                                                        'Generator:min_kw',
                                                        'dieselMin',
                                                        'Specify minimum fossil generation in kW. Only specify if needed, as the optimization runs best if left unedited.',
                                                        1.0e6,
                                                        0),
                min_turn_down_pct:                  new REoptFloatParameter(
                                                        'Min Gen Loading (% as decimal)',
                                                        'Generator:min_turn_down_pct',
                                                        'minGenLoading',
                                                        'Please enter a number 0-1 for the the minimum fraction of rated total kVA load that must be maintained by the generator. >/= 0.3 recommended for extended diesel operation. Set to 0 for highest likelihood of success in solving optimization. Format 0.XX',
                                                        1,
                                                        0),
                om_cost_per_kw:                     new REoptFloatParameter(
                                                        'Genset Annual O+M Cost ($/kW/year)',
                                                        'Generator:om_cost_per_kw',
                                                        'dieselOMCostKw',
                                                        'Specify annual operations and maintenance cost per kilowatt per year.',
                                                        1.0e9,
                                                        0),
                om_cost_per_kwh:                    new REoptFloatParameter(
                                                        'Genset Hourly O+M Cost ($/kWh/year)',
                                                        'Generator:om_cost_per_kwh',
                                                        'dieselOMCostKwh',
                                                        'Specify annual operations and maintenance cost per kilowatt-hour per year. Format "X.XX"',
                                                        1.0e9,
                                                        0),
            },
            PV: {
                can_curtail:                    new REoptBooleanParameter(
                                                    'DG Can Curtail',
                                                    'PV:can_curtail',
                                                    'solarCanCurtail',
                                                    'Allows for excess distributed generation to be automatically curtailed.'),
                can_export_beyond_nem_limit:    new REoptBooleanParameter(
                                                    'DG Can Export',
                                                    'PV:can_export_beyond_nem_limit',
                                                    'solarCanExport',
                                                    'Allows for excess distributed generation to be sold back to the grid.'),
                federal_itc_pct:                new REoptFloatParameter(
                                                    'Solar ITC (% as decimal)',
                                                    'PV:federal_itc_pct',
                                                    'solarItcPercent',
                                                    'Please enter a number 0-1 for the solar investment tax credit. Format 0.XX',
                                                    1,
                                                    0),
                installed_cost_per_kw:          new REoptFloatParameter(
                                                    'Solar Cost ($/kW-DC)',
                                                    'PV:installed_cost_per_kw',
                                                    'solarCost',
                                                    'Specify the cost in $/kW-DC.',
                                                    1.0e9,
                                                    0),
                macrs_option_years:             new REoptIntParameter(
                                                    'Solar MACRS Years',
                                                    'PV:macrs_option_years',
                                                    'solarMacrsOptionYears',
                                                    'MACRS schedule for financial analysis. Possible inputs are 0, 5 and 7 years. Set to zero to disable accelerated depreciation accounting for solar.',
                                                    100,
                                                    0),
                max_kw:                         new REoptFloatParameter(
                                                    'Solar Power Max (kW-DC)',
                                                    'PV:max_kw',
                                                    'solarMax',
                                                    'Specify the maximum desired generation in kW-DC. Leave at default for full optimization on solar power.',
                                                    1.0e9,
                                                    0),
                mgu_enabled:                    new REoptBooleanParameter(
                                                    'Solar',
                                                    'PV:mgu_enabled',
                                                    'solar',
                                                    'Specify whether solar should be a part of the microgrid design.'),
                min_kw:                         new REoptFloatParameter(
                                                    'Solar Power Min (kW-DC)',
                                                    'PV:min_kw',
                                                    'solarMin',
                                                    'Specify the minimum desired generation in kW-DC.',
                                                    1.0e9,
                                                    0),
            },
            Wind: {
                federal_itc_pct:        new REoptFloatParameter(
                                            'Wind ITC (% as decimal)',
                                            'Wind:federal_itc_pct',
                                            'windItcPercent',
                                            'Please enter a number 0-1 for the wind investment tax credit. Format 0.XX',
                                            1,
                                            0),
                installed_cost_per_kw:  new REoptFloatParameter(
                                            'Wind Cost ($/kW)',
                                            'Wind:installed_cost_per_kw',
                                            'windCost',
                                            'Specify the cost in $/kW.',
                                            1.0e9,
                                            0),
                macrs_option_years:     new REoptIntParameter(
                                            'Wind MACRS Years',
                                            'Wind:macrs_option_years',
                                            'windMacrsOptionYears',
                                            'MACRS schedule for financial analysis. Possible inputs are 0, 5 and 7 years. Set to zero to disable accelerated depreciation accounting for solar.',
                                            100,
                                            0),
                max_kw:                 new REoptFloatParameter(
                                            'Wind Power Max (kW)',
                                            'Wind:max_kw',
                                            'windMax',
                                            'Specify the maximum desired generation in kW. Leave at default for full optimization on wind power.',
                                            1.0e9,
                                            0),
                mgu_enabled:            new REoptBooleanParameter(
                                            'Wind',
                                            'Wind:mgu_enabled',
                                            'wind',
                                            'Specify whether wind should be a part of the microgrid design.'),
                min_kw:                 new REoptFloatParameter(
                                            'Wind Power Min (kW)',
                                            'Wind:min_kw',
                                            'windMin',
                                            'Specify the minimum desired generation in kW.',
                                            1.0e9,
                                            0)
            },
            MicrogridUp: {
                singlePhaseRelayCost: new REoptFloatParameter(
                                        'Single-Phase Relay Cost ($)',
                                        'MicrogridUp:singlePhaseRelayCost',
                                        'singlePhaseRelayCost',
                                        'Specify the cost of a single-phase relay in $.',
                                        1.0e9,
                                        0),
                threePhaseRelayCost: new REoptFloatParameter(
                                        'Three-Phase Relay Cost ($)',
                                        'MicrogridUp:threePhaseRelayCost',
                                        'threePhaseRelayCost',
                                        'Specify the cost of a three-phase relay in $.',
                                        1.0e9,
                                        0),
            }
        }
    }

    /**
     * - I need to be able to add parameters to the model so that they can't be overridden on a per-microgrid basis but they can be validated
     * @param {string} parameterName - a string of the form "<REopt parameter namespace>:<REopt parameter name>"
     * @param {REoptParameter} parameter - a REopt parameter
     */
    addReoptParameter(parameterName, parameter) {
        if (typeof parameterName !== 'string') {
            throw TypeError('The "parameter" argument must be typeof "string".');
        }
        if (!(parameter instanceof REoptParameter)) {
            throw TypeError('The "parameter" argument must be instanceof REoptParameter');
        }
        const [type, name] = parameterName.split(':');
        if (!Object.hasOwn(this.#reoptParameters, type)) {
            throw Error(`The parameter namespace "${type}" does not exist.`);
        }
        if (Object.hasOwn(this.#reoptParameters[type], name)) {
            throw Error(`The parameter "${name}" already exists.`);
        }
        this.#reoptParameters[type][name] = parameter;
    }

    /**
     * @param {string} parameterName - a string of the form "<REopt parameter namespace>:<REopt parameter name>"
     * @returns {REoptParameter}
     */
    getReoptParameter(parameterName) {
        if (typeof parameterName !== 'string') {
            throw TypeError('The "parameter" argument must be typeof "string".');
        }
        const [type, name] = parameterName.split(':');
        if (!Object.hasOwn(this.#reoptParameters, type) || !Object.hasOwn(this.#reoptParameters[type], name)) {
            throw Error(`The parameter "${parameterName}" does not exist.`);
        }
        return this.#reoptParameters[type][name];
    }

    /**
     * @returns {Array}
     */
    get reoptParameters() {
        const parameters = [];
        for (const namespace of Object.values(this.#reoptParameters)) {
            for (const parameter of Object.values(namespace)) {
                parameters.push(parameter);
            }
        }
        parameters.sort((a, b) => a.displayName.localeCompare(b.displayName, 'en'));
        return parameters;
    }

    set reoptParameters(reoptParameters) {
        throw Error('read-only accessor descriptor');
    }

    /**
     * @param {string} id - a string of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
     *  What changed? The value of a parameter. Which parameter changed? The one with the matching ID. What was the previous value of the parameter
     *  before the changed occurred? oldValue
     * @param {object} oldValue
     * @returns {undefined}
     */
    notifyObserversOfChangedProperty(id, oldValue) {
        for (const observer of this.observers) {
            observer.handleChangedProperty(this, id, oldValue);
        }
    }
}

/*
interface REoptParameter {
    +(get)displayName
    +(get)parameterName
    +(get)value
    +(set)value
}
*/
class REoptParameter {

    #alias;
    #displayName;
    #parameterName;
    #tooltip;
    #value;

    constructor(displayName, parameterName, alias, tooltip) {
        if (typeof displayName !== 'string') {
            throw TypeError('The "displayName" argument must be typeof "string".');
        }
        if (typeof parameterName !== 'string') {
            throw TypeError('The "parameterName" argument must be typeof "string".');
        }
        if (parameterName.split(':').length !== 2) {
            throw Error(`The "parameterName" argument "${parameterName}" must contain exactly one ":" character.`);
        }
        if (typeof alias !== 'string') {
            throw TypeError('The "alias" argument must be typeof "string".');
        }
        if (typeof tooltip !== 'string') {
            throw TypeError('The "tooltip" argument must be typeof "string".');
        }
        this.#displayName = displayName;
        this.#parameterName = parameterName;
        this.#alias = alias;
        this.#tooltip = tooltip;
        this.#value = null;
    }

    /**
     * @returns {string}
     */
    get alias() {
        return this.#alias;
    }

    set alias(alias) {
        throw Error('read-only accessor descriptor.');
    }

    /**
     * @returns {string}
     */
    get displayName() {
        return this.#displayName;
    }

    set displayName(displayName) {
        throw Error('read-only accessor descriptor.');
    }

    /**
     * @returns {string}
     */
    get parameterName() {
        return this.#parameterName;
    }

    set parameterName(parameterName) {
        throw Error('read-only accessor descriptor.');
    }

    /**
     * @returns {string}
     */
    get tooltip() {
        return this.#tooltip;
    }

    set tooltip(tooltip) {
        throw Error('read-only accessor descriptor.');
    }

    /**
     * @returns {object}
     */
    get value() {
        return this.#value;
    }

    /**
     * @param {object} value
     * @returns {undefined}
     */
    set value(value) {
        this.#value = value;
    }

    isSet() {
        return this.#value !== null;
    }

    unset() {
        this.#value = null;
    }
}

class REoptIntParameter extends REoptParameter {
    #max;
    #min;

    constructor(displayName, parameterName, alias, tooltip, max, min) {
        if (typeof max !== 'number') {
            throw TypeError('The "max" argument must be typeof "number".');
        }
        if (typeof min !== 'number') {
            throw TypeError('The "min" argument must be typeof "number".');
        }
        if (max < min) {
            throw Error('The "max" argument must be greater than the "min" argument.');
        }
        super(displayName, parameterName, alias, tooltip);
        this.#max = max;
        this.#min = min;
    }

    /**
     * @returns {number}
     */
    get value() {
        return super.value;
    }

    /**
     * @param {number} value
     * @returns {undefined}
     */
    set value(value) {
        if (typeof value !== 'number') {
            throw TypeError(`"${this.displayName}" must be typeof "number".`);
        }
        if (!Number.isInteger(value)) {
            throw TypeError(`"${this.displayName}" must be an integer.`);
        }
        if (value > this.#max) {
            throw Error(`"${this.displayName}" must be <= ${this.#max}.`)
        }
        if (value < this.#min) {
            throw Error(`"${this.displayName}" must be >= ${this.#min}.`)
        }
        super.value = value;
    }
}

class REoptFloatParameter extends REoptParameter {
    #max;
    #min;

    constructor(displayName, parameterName, alias, tooltip, max, min) {
        if (typeof max !== 'number') {
            throw TypeError('The "max" argument must be typeof "number".');
        }
        if (typeof min !== 'number') {
            throw TypeError('The "min" argument must be typeof "number".');
        }
        if (max < min) {
            throw Error('The "max" argument must be greater than the "min" argument.');
        }
        super(displayName, parameterName, alias, tooltip);
        this.#max = max;
        this.#min = min;
    }

    /**
     * @returns {number}
     */
    get value() {
        return super.value;
    }

    /**
     * @param {number} value
     * @returns {number}
     */
    set value(value) {
        if (typeof value !== 'number') {
            throw TypeError(`"${this.displayName}" must be typeof "number".`);
        }
        if (isNaN(value)) {
            throw TypeError(`"${this.displayName}" must not be NaN.`);
        }
        if (value > this.#max) {
            throw Error(`"${this.displayName}" must be <= ${this.#max}.`);
        }
        if (value < this.#min) {
            throw Error(`"${this.displayName}" must be >= ${this.#min}.`);
        }
        super.value = value;
    }
}

class REoptStringParameter extends REoptParameter {

    #regex;

    constructor(displayName, parameterName, alias, tooltip, regex) {
        super(displayName, parameterName, alias, tooltip);
        if (!(regex instanceof RegExp)) {
            throw TypeError('The "regex" argument must be instance of RegExp.');
        }
        this.#regex = regex;
    }

    /**
     * @returns {string}
     */
    get value() {
        return super.value;
    }

    /**
     * @param {string} value
     * @returns {undefined}
     */
    set value(value) {
        if (typeof value !== 'string') {
            throw TypeError('The "value" argument must be typeof "string".');
        }
        if (!this.#regex.test(value)) {
            throw Error(`"${value}" must match the format description.`);
        }
        super.value = value;
    }
}

class REoptJsonObjectParameter extends REoptParameter {

    #requiredKeys;
    #placeholder;

    /**
     * @param {string} displayName
     * @param {string} parameterName
     * @param {string} alias
     * @param {string} tooltip
     * @param {Array} requiredKeys - keys the parsed object must have
     * @param {string} [placeholder=''] - example text shown in the empty textarea
     */
    constructor(displayName, parameterName, alias, tooltip, requiredKeys, placeholder='') {
        super(displayName, parameterName, alias, tooltip);
        if (!Array.isArray(requiredKeys) || requiredKeys.some(key => typeof key !== 'string')) {
            throw TypeError('The "requiredKeys" argument must be an array of strings.');
        }
        if (typeof placeholder !== 'string') {
            throw TypeError('The "placeholder" argument must be typeof "string".');
        }
        this.#requiredKeys = [...requiredKeys];
        this.#placeholder = placeholder;
    }

    /**
     * @returns {Array}
     */
    get requiredKeys() {
        return [...this.#requiredKeys];
    }

    /**
     * @returns {string}
     */
    get placeholder() {
        return this.#placeholder;
    }

    /**
     * @returns {string}
     */
    get value() {
        return super.value;
    }

    /**
     * @param {string} value - JSON text, or an empty string for "not provided"
     * @returns {undefined}
     */
    set value(value) {
        if (typeof value !== 'string') {
            throw TypeError('The "value" argument must be typeof "string".');
        }
        const text = value.trim();
        if (text !== '') {
            let object;
            try {
                object = JSON.parse(text);
            } catch (e) {
                throw Error(`"${this.displayName}" must be valid JSON (${e.message}).`);
            }
            if (typeof object !== 'object' || object === null || Array.isArray(object)) {
                throw Error(`"${this.displayName}" must be a JSON object.`);
            }
            const missingKeys = this.#requiredKeys.filter(key => !Object.hasOwn(object, key));
            if (missingKeys.length > 0) {
                const hint = Object.hasOwn(object, 'items') ? ' If you pasted an OpenEI API response, paste only the rate object inside "items".' : '';
                throw Error(`"${this.displayName}" is missing required keys: ${missingKeys.join(', ')}.${hint}`);
            }
        }
        super.value = text;
    }
}

class REoptBooleanParameter extends REoptParameter {

    constructor(displayName, parameterName, alias, tooltip) {
        super(displayName, parameterName, alias, tooltip);
    }

    /**
     * @returns {boolean}
     */
    get value() {
        return super.value;
    }

    /**
     * @param {boolean} value
     * @returns {undefined}
     */
    set value(value) {
        if (typeof value !== 'boolean') {
            throw TypeError('The "value" argument must be typeof "boolean".');
        }
        super.value = value;
    }
}