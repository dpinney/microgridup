export { REoptParametersModel, REoptParameters, REoptParameter, REoptIntParameter, REoptFloatParameter, REoptStringParameter, REoptBooleanParameter };
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
        throw Error('readonly accessor descriptor');
    }

    /**
     * @param {string} reoptParametersInstanceName - the name of a microgrid
     * @returns {undefined}
     */
    addReoptParametersInstance(reoptParametersInstanceName) {
        if (typeof reoptParametersInstanceName !== 'string') {
            throw TypeError('The "name" argument must be typeof "string".');
        }
        if (Object.hasOwn(this.#reoptParametersInstances, reoptParametersInstanceName)) {
            throw Error('The "name" argument already exists');
        }
        this.#reoptParametersInstances[reoptParametersInstanceName] = new REoptParameters();
    }

    /**
     * @param {string} reoptParametersInstanceName
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
                year: new REoptIntParameter('Year', 'ElectricLoad:year', 'year', 2100, 1900)
            },
            ElectricStorage: {
                battery_replacement_year:   new REoptIntParameter('Battery capacity replacement year', 'ElectricStorage:battery_replacement_year', 'batteryCapacityReplaceYear', 100, 0),
                installed_cost_per_kw:      new REoptFloatParameter('Battery power cost per kW', 'ElectricStorage:installed_cost_per_kw', 'batteryPowerCost', 1.0e9, 0),
                installed_cost_per_kwh:     new REoptFloatParameter('Battery capacity cost per kWh', 'ElectricStorage:installed_cost_per_kwh', 'batteryCapacityCost', 1.0e9, 0),
                inverter_replacement_year:  new REoptIntParameter('Battery power replacement year', 'ElectricStorage:inverter_replacement_year', 'batteryPowerReplaceYear', 100, 0),
                macrs_option_years:         new REoptIntParameter('Battery macrs option years', 'ElectricStorage:macrs_option_years', 'batteryMacrsOptionYears', 100, 0),
                max_kw:                     new REoptFloatParameter('Battery power max kW', 'ElectricStorage:max_kw', 'batteryPowerMax', 1.0e4, 0),
                max_kwh:                    new REoptFloatParameter('Battery capacity max kWh', 'ElectricStorage:max_kwh', 'batteryCapacityMax', 1.0e6, 0),
                mgu_enabled:                new REoptBooleanParameter('Batteries are enabled', 'ElectricStorage:mgu_enabled', 'battery'),
                min_kw:                     new REoptFloatParameter('Battery power min kW', 'ElectricStorage:min_kw', 'batteryPowerMin', 1.0e4, 0),
                min_kwh:                    new REoptFloatParameter('Battery capacity min kWh', 'ElectricStorage:min_kwh', 'batteryCapacityMin', 1.0e6, 0),
                total_itc_pct:              new REoptFloatParameter('Battery itc percent (as decimal)', 'ElectricStorage:total_itc_pct', 'batteryItcPercent', 1, 0),
                replace_cost_per_kw:        new REoptFloatParameter('Battery power replacement cost per kW', 'ElectricStorage:replace_cost_per_kw', 'batteryPowerCostReplace', 1.0e9, 0),
                replace_cost_per_kwh:       new REoptFloatParameter('Battery capacity replacement cost per kWh', 'ElectricStorage:replace_cost_per_kwh', 'batteryCapacityCostReplace', 1.0e9, 0)
            },
            ElectricTariff: {
                blended_annual_energy_rate: new REoptFloatParameter('Energy cost', 'ElectricTariff:blended_annual_energy_rate', 'energyCost', 1.0e9, 0),
                blended_annual_demand_rate: new REoptFloatParameter('Demand cost', 'ElectricTariff:blended_annual_demand_rate', 'demandCost', 1.0e9, 0),
                urdb_label:                 new REoptStringParameter('URDB label', 'ElectricTariff:urdb_label', 'urdbLabel'),
                mgu_urdb_label_enabled:     new REoptBooleanParameter('URDB label is enabled', 'ElectricTariff:mgu_urdb_label_enabled', 'urdbLabelSwitch'),
                wholesale_rate:             new REoptFloatParameter('Wholesale cost', 'ElectricTariff:wholesale_rate', 'wholesaleCost', 1.0e9, 0),
            },
            Financial: {
                analysis_years:             new REoptIntParameter('Analysis years', 'Financial:analysis_years', 'analysisYears', 100, 0),
                offtaker_discount_pct:      new REoptFloatParameter('Discount rate percent (as decimal)', 'Financial:offtaker_discount_pct', 'discountRate', 1, 0),
                om_cost_escalation_pct:     new REoptFloatParameter('OM cost escalator percent (as decimal)', 'Financial:om_cost_escalation_pct', 'omCostEscalator', 1, 0),
                value_of_lost_load_per_kwh: new REoptFloatParameter('Value of lost load', 'Financial:value_of_lost_load_per_kwh', 'value_of_lost_load', 1.0e9, 0),
            },
            Generator: {
                emissions_factor_lb_CO2_per_gal:    new REoptFloatParameter('Fossil CO2 factor', 'Generator:emissions_factor_lb_CO2_per_gal', 'dieselCO2Factor', 1.0e9, 0),
                only_runs_during_grid_outage:       new REoptBooleanParameter('Fossil only runs during outage', 'Generator:only_runs_during_grid_outage', 'dieselOnlyRunsDuringOutage'),
                fuel_avail_gal:                     new REoptFloatParameter('Fossil fuel gallons available', 'Generator:fuel_avail_gal', 'fuelAvailable', 1.0e9, 0),
                fuel_cost_per_gallon:               new REoptFloatParameter('Fossil fuel cost per gallon', 'Generator:fuel_cost_per_gallon', 'dieselFuelCostGal', 1.0e9, 0),
                installed_cost_per_kw:              new REoptFloatParameter('Fossil cost per kW', 'Generator:installed_cost_per_kw', 'dieselGenCost', 1.0e9, 0),
                macrs_option_years:                 new REoptIntParameter('Fossil macrs option years', 'Generator:macrs_option_years', 'dieselMacrsOptionYears', 100, 0),
                max_kw:                             new REoptFloatParameter('Fossil max kW', 'Generator:max_kw', 'dieselMax', 1.0e6, 0),
                mgu_enabled:                        new REoptBooleanParameter('Fossil is enabled', 'Generator:mgu_enabled', 'fossil'),
                min_kw:                             new REoptFloatParameter('Fossil min kW', 'Generator:min_kw', 'dieselMin', 1.0e6, 0),
                min_turn_down_pct:                  new REoptFloatParameter('Fossil min generator loading percent (as decimal)', 'Generator:min_turn_down_pct', 'minGenLoading', 1, 0),
                om_cost_per_kw:                     new REoptFloatParameter('Fossil om cost per kW', 'Generator:om_cost_per_kw', 'dieselOMCostKw', 1.0e9, 0),
                om_cost_per_kwh:                    new REoptFloatParameter('Fossil om cost per kWh', 'Generator:om_cost_per_kwh', 'dieselOMCostKwh', 1.0e9, 0),
            },
            PV: {
                can_curtail:                    new REoptBooleanParameter('Solar can curtail', 'PV:can_curtail', 'solarCanCurtail'),
                can_export_beyond_nem_limit:    new REoptBooleanParameter('Solar can export', 'PV:can_export_beyond_nem_limit', 'solarCanExport'),
                federal_itc_pct:                new REoptFloatParameter('Solar itc percent', 'PV:federal_itc_pct', 'solarItcPercent', 1, 0),
                installed_cost_per_kw:          new REoptFloatParameter('Solar cost per kW', 'PV:installed_cost_per_kw', 'solarCost', 1.0e9, 0),
                macrs_option_years:             new REoptIntParameter('Solar macrs option years', 'PV:macrs_option_years', 'solarMacrsOptionYears', 100, 0),
                max_kw:                         new REoptFloatParameter('Solar max kW', 'PV:max_kw', 'solarMax', 1.0e9, 0),
                mgu_enabled:                    new REoptBooleanParameter('Solar is enabled', 'PV:mgu_enabled', 'solar'),
                min_kw:                         new REoptFloatParameter('Solar min kW', 'PV:min_kw', 'solarMin', 1.0e9, 0),
            },
            Wind: {
                federal_itc_pct:        new REoptFloatParameter('Wind itc percent', 'Wind:federal_itc_pct', 'windItcPercent', 1, 0),
                installed_cost_per_kw:  new REoptFloatParameter('Wind cost per kW', 'Wind:installed_cost_per_kw', 'windCost', 1.0e9, 0),
                macrs_option_years:     new REoptIntParameter('Wind macrs option years', 'Wind:macrs_option_years', 'windMacrsOptionYears', 100, 0),
                max_kw:                 new REoptFloatParameter('Wind max kW', 'Wind:max_kw', 'windMax', 1.0e9, 0),
                mgu_enabled:            new REoptBooleanParameter('Wind is enabled', 'Wind:mgu_enabled', 'wind'),
                min_kw:                 new REoptFloatParameter('Wind min kW', 'Wind:min_kw', 'windMin', 1.0e9, 0)
            },
            MicrogridUp: {
                singlePhaseRelayCost: new REoptFloatParameter('Single-phase relay cost', 'MicrogridUp:singlePhaseRelayCost', 'singlePhaseRelayCost', 1.0e9, 0),
                threePhaseRelayCost: new REoptFloatParameter('Three-phase relay cost', 'MicrogridUp:threePhaseRelayCost', 'threePhaseRelayCost', 1.0e9, 0)
            }
        }
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
        throw Error('readonly accessor descriptor');
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
    #value;

    constructor(displayName, parameterName, alias) {
        if (typeof alias !== 'string') {
            throw TypeError('The "alias" argument must be typeof "string".');
        }
        if (typeof displayName !== 'string') {
            throw TypeError('The "displayName" argument must be typeof "string".');
        }
        if (typeof parameterName !== 'string') {
            throw TypeError('The "parameterName" argument must be typeof "string".');
        }
        if (parameterName.split(':').length !== 2) {
            throw Error(`The "parameterName" argument "${parameterName}" must contain exactly one ":" character`);
        }
        this.#alias = alias;
        this.#displayName = displayName;
        this.#parameterName = parameterName;
        this.#value = null;
    }

    /**
     * @returns {string}
     */
    get alias() {
        return this.#alias;
    }

    set alias(alias) {
        throw Error('readonly accessor descriptor');
    }

    /**
     * @returns {string}
     */
    get displayName() {
        return this.#displayName;
    }

    set displayName(displayName) {
        throw Error('readonly accessor descriptor');
    }

    /**
     * @returns {string}
     */
    get parameterName() {
        return this.#parameterName;
    }

    set parameterName(parameterName) {
        throw Error('readonly accessor descriptor');
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

    constructor(displayName, parameterName, alias, max, min) {
        if (typeof max !== 'number') {
            throw TypeError('The "max" argument must be typeof "number".');
        }
        if (typeof min !== 'number') {
            throw TypeError('The "min" argument must be typeof "number".');
        }
        if (max < min) {
            throw Error('The "max" argument must be greater than the "min" argument.');
        }
        super(displayName, parameterName, alias);
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
            throw TypeError(`The value given for "${this.displayName}" must be typeof "number".`);
        }
        if (!Number.isInteger(value)) {
            throw TypeError(`The value given for "${this.displayName}" must be an integer.`);
        }
        if (value > this.#max) {
            throw Error(`The value given for "${this.displayName}" must be <= ${this.#max}`)
        }
        if (value < this.#min) {
            throw Error(`The value given for "${this.displayName}" must be >= ${this.#min}`)
        }
        super.value = value;
    }
}

class REoptFloatParameter extends REoptParameter {
    #max;
    #min;

    constructor(displayName, parameterName, alias, max, min) {
        if (typeof max !== 'number') {
            throw TypeError('The "max" argument must be typeof "number".');
        }
        if (typeof min !== 'number') {
            throw TypeError('The "min" argument must be typeof "number".');
        }
        if (max < min) {
            throw Error('The "max" argument must be greater than the "min" argument.');
        }
        super(displayName, parameterName, alias);
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
            throw TypeError(`The value given for "${this.displayName}" must be typeof "number".`);
        }
        if (isNaN(value)) {
            throw TypeError(`The value given for "${this.displayName}" must not be NaN.`);
        }
        if (value > this.#max) {
            throw Error(`The value given for "${this.displayName}" must be <= ${this.#max}`);
        }
        if (value < this.#min) {
            throw Error(`The value given for "${this.displayName}" must be >= ${this.#min}`);
        }
        super.value = value;
    }
}

class REoptStringParameter extends REoptParameter {

    constructor(displayName, parameterName, alias) {
        super(displayName, parameterName, alias);
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
        super.value = value.trim();
    }
}

class REoptBooleanParameter extends REoptParameter {

    constructor(displayName, parameterName, alias) {
        super(displayName, parameterName, alias);
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