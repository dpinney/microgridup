export { REoptParametersController };
import { REoptParametersModel } from './model.js';

/**
 * - A controller is useful because:
 *  - It has a reference to the model that the view can use to get state, so I always need a controller class
 *  - It is always a tool for a view to modify the model, so I always need a controller class
 */
class REoptParametersController {

    model;

    constructor(model) {
        if (!(model instanceof REoptParametersModel)) {
            throw TypeError('The "model" argument must be instanceof REoptParametersModel.');
        }
        this.model = model;
    }

    /**
     * - A controller can modify any aspect of the model. It's a view's job to tell the controller what part(s) of the model it wants to change
     * @param {string} id - a string of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
     * @param {object} value
     * @returns {undefined}
     */
    setParameterValue(id, value) {
        if (typeof id !== 'string') {
            throw TypeError('The "id" argument must be typeof "string".');
        }
        const [microgridName, parameterNamespace, name] = id.split(':');
        try {
            const reoptParametersInstance = this.model.getReoptParametersInstance(microgridName);
            const parameter = reoptParametersInstance.getReoptParameter(`${parameterNamespace}:${name}`);
            const oldValue = parameter.value;
            parameter.value = value;
            reoptParametersInstance.notifyObserversOfChangedProperty(id, oldValue);
        } catch (e) {
            throw e;
        }
    }

    /**
     * @param {string} id - a string of the form "<microgrid name>:<REopt parameter namespace>:<REopt parameter name>"
     * @returns {undefined}
     */
    unsetParameter(id) {
        if (typeof id !== 'string') {
            throw TypeError('The "id" argument must be typeof "string".');
        }
        const [microgridName, parameterNamespace, name] = id.split(':');
        try {
            const reoptParametersInstance = this.model.getReoptParametersInstance(microgridName);
            const parameter = reoptParametersInstance.getReoptParameter(`${parameterNamespace}:${name}`);
            const oldValue = parameter.value;
            parameter.unset();
            reoptParametersInstance.notifyObserversOfChangedProperty(id, oldValue);
        } catch (e) {
            throw e;
        }
    }
}

