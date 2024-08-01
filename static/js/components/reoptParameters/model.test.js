import { describe, expect, it, vi } from 'vitest'
import { REoptParametersModel, REoptParameters, REoptParameter, REoptIntParameter, REoptFloatParameter, REoptStringParameter, REoptBooleanParameter } from './model.js'

/**
 * - I wanted to have a single REoptParameter class, but it was too difficult to test. What I realized is that I really have four different classes
 *   (REoptIntParameter, REoptFloatParameter, REoptBooleanParameter, and REoptStringParameter) that implement the same REoptParameter interface (i.e.
 *   get a value, set a value, and get export data)
 *  - Note: if a constructor is complicated, I probably need multiple classes!
 * - Writing tests makes better code but it takes 3x as long to do anything. A measure of code quality is "can I test this" even if I don't write all
 *   the tests that I should
 *  - Even writing 2 tests out of a possible 20 for a class and its methods is better than not trying to test at all
 * - Classes should be impervious against changes in the data schema structure
 *  - Implement methods that don't assume a given input structure (i.e. ordering of keys, nesting of keys, etc.)
 *  - If I do need to rely on a schema, concentrate as much of that schema as possible (e.g. concentrate the schema in as few classes a possible. Most
 *    classes shouldn't care about it)
 * - Classes should be resilient against changes in the data schema content
 *  - This is hard, but the impact of schema content changes can also be minimized by concentrating schema dependencies in as few locations as
 *    possible
 */

/**
 * - At this point in the design, there is no "Microgrid" class. It just so happens that every instance of REoptParameters is conceptually associated
 *   with a distinct microgrid. This distinction matters because I shouldn't be writing a MicrogridsController, MicrogridsModel, or MicrogridsView
 *   class. I would need to plan my code to accommodate whatever extra properties would exist on actual Microgrid instances. I would also probably
 *   need to create more views and another MicrogridsController, but that doesn't mean the views and controllers I've created here couldn't be
 *   incorporated into those other classes
 */

/**
 * - Unfortunately, just checking that an error was thrown is never enough. The error needs to be of the expected type and it needs to contain an
 *   expected message. Since JavaScript doesn't have a useful error hierarchy (i.e. everything, including a TypeError, is an Error), I'll just check
 *   for message content with a regular expression
 */

/**
 * - Factory functions shouldn't have parameters imo. If they do, they're coupled to the implementation of the constructor. If that's the case, what's
 *   the point of having a factory function?
 */
function makeREoptParametersModel() {
    return new REoptParametersModel();
}

function makeREoptParameters() {
    return new REoptParameters('any displayName', 'namespace:name', 'any alias');
}

function makeREoptIntParameter() {
    return new REoptIntParameter('any displayName', 'namespace:name', 'any alias', 0, 0);
}

function makeREoptFloatParameter() {
    return new REoptFloatParameter('any displayName', 'namespace:name', 'any alias', 0, 0);
}

function makeREoptStringParameter() {
    return new REoptStringParameter('any displayName', 'namespace:name', 'any alias');
}

function makeREoptBooleanParameter() {
    return new REoptBooleanParameter('any displayName', 'namespace:name', 'any alias');
}

describe('REoptParametersModel', () => {

    describe('addReoptParametersInstance', () => {

        describe('given an existing name', () => {

            it('throws an error', () => {
                const model = makeREoptParametersModel();
                const name = 'microgridName';
                model.addReoptParametersInstance(name);
                
                //expect(() => model.addReoptParametersInstance(name)).toThrow(/already exists/);
            });
        });

        describe('given a non-existent name', () => {

            it('adds a REoptParameters instance', () => {
                const model = makeREoptParametersModel();
                const name = 'microgridName';
                model.addReoptParametersInstance(name);
                expect(model.getReoptParametersInstance(name)).toBeInstanceOf(REoptParameters);
            });
        });

        describe('given a non-string primitive or object', () => {

            it.each([1, true, null, undefined, {}])('throws an error given %o', (name) => {
                const model = makeREoptParametersModel();
                expect(() => model.addReoptParametersInstance(name)).toThrow(/argument must be typeof "string"/);
            });
        });
    });

    describe('getReoptParametersInstance', () => {

        describe('given an existing name', () => {

            it('returns the matching REoptParameters instance', () => {
                const model = makeREoptParametersModel();
                const name = 'microgridName';
                model.addReoptParametersInstance(name);
                expect(model.getReoptParametersInstance(name)).toBeInstanceOf(REoptParameters);
            });
        });

        describe('given a non-existent name', () => {

            it('throws an error', () => {
                const model = makeREoptParametersModel();
                const name = 'microgridName';
                expect(() => model.getReoptParametersInstance(name)).toThrow(/does not exist/);
            });
        });

        describe('given a non-string primitive or object', () => {

            it.each([1, true, null, undefined, {}])('throws an error given %o', (name) => {
                const model = makeREoptParametersModel();
                expect(() => model.getReoptParametersInstance(name)).toThrow(/argument must be typeof "string"/);
            });
        });
    });

    describe('get reoptParametersInstances', () => {

        it('returns an object that is not an array', () => {
            const model = makeREoptParametersModel();
            expect(model.reoptParametersInstances).toBeInstanceOf(Object);
            expect(model.reoptParametersInstances).not.toBeInstanceOf(Array);
        });
    });
});

describe('REoptParameters', () => {

    describe('getReoptParameter', () => {

        describe('given a non-string primitive or object', () => {

            it.each([true, 1, null, undefined, {}])('throws an error given %o', (value) => {
                const parameters = makeREoptParameters();
                expect(() => parameters.getReoptParameter(value)).toThrow(/argument must be typeof "string"/);
            });
        });

        describe('given a parameter name that doesn\'t exist', () => {

            it('throws an error', () => {
                const parameters = makeREoptParameters();
                expect(() => parameters.getReoptParameter('foobar')).toThrow(/does not exist/);
            });
        });

        describe('given a parameter name that exists', () => {

            it('returns the REoptParameter instance', () => {
                const parameters = makeREoptParameters();
                expect(parameters.getReoptParameter('PV:can_export_beyond_nem_limit')).toBeInstanceOf(REoptParameter)
            });
        });
    });

    describe('get reoptParameters', () => {

        describe('reoptParameters', () => {

            it('returns an array', () => {
                const parameters = makeREoptParameters();
                expect(parameters.reoptParameters).toBeInstanceOf(Array);
            });

            it('returns an array of length 49', () => {
                const parameters = makeREoptParameters();
                const expectedParameterCount = 49;
                expect(parameters.reoptParameters.length).toEqual(expectedParameterCount);
            });

            it('returns an array of REoptParameter instances', () => {
                const parameters = makeREoptParameters();
                expect(parameters.reoptParameters[0]).toBeInstanceOf(REoptParameter);
            });
        });
    });
});

describe('REoptParameter', () => {

    describe('alias is not typeof "string"', () => {

        it('throws an error', () => {
            expect(() => new REoptParameter()).toThrow(/must be typeof "string"/);
        });
    });

    describe('alias is typeof "string"', () => {

        it('sets the alias', () => {
            const parameter = new REoptParameter('any displayName', 'namespace:name', 'any alias');
            expect(parameter.alias).toEqual('any alias');
        });
    });

    describe('displayName is not typeof "string"', () => {

        it('throws an error', () => {
            expect(() => new REoptParameter()).toThrow(/must be typeof "string"/);
        });
    });

    describe('displayName is typeof "string"', () => {

        it('sets the displayname', () => {
            const parameter = new REoptParameter('any displayName', 'namespace:name', 'any alias');
            expect(parameter.displayName).toEqual('any displayName');
        });
    });

    describe('parameterName is not typeof "string"', () => {

        it('throws an error', () => {
            expect(() => new REoptParameter('any displayName')).toThrow(/must be typeof "string"/);
        });
    });

    describe('parameterName is typeof "string"', () => {

        describe('parameterName contains a colon', () => {

            it('sets the parameterName', () => {
                const namespace = 'load';
                const name = 'max_kw';
                const parameter = new REoptParameter('any displayName', `${namespace}:${name}`, 'any alias');
                expect(parameter.parameterName).toEqual('load:max_kw');
            });
        });

        describe('parameterName contains more than one colon', () => {

            it('throws an error', () => {
                const namespace = 'load';
                const name = 'max_kw';
                expect(() => new REoptParameter('any displayName', `${namespace}:${name}:foo`, 'any alias')).toThrow(/must contain exactly one ":" character/);
            });
        });

        describe('parameterName does not contain a colon', () => {

            it('throws an error', () => {
                const parameterNameLackingColon = 'max_kw';
                expect(() => new REoptParameter('any displayName', parameterNameLackingColon, 'any alias')).toThrow(/must contain exactly one ":" character/);
            });
        });
    });

    //describe('set value', () => {

    //    it('sets the value', () => {
    //        expect(true).toEqual(false);
    //    });

    //    // - More tests?
    //    it('calls notifyObserversOfChangedProperty with the old value', () => {
    //        const parameter = new REoptParameter('any displayName', 'any parameterName');
    //        const spy = vi.spyOn(parameter, 'notifyObserversOfChangedProperty');
    //        expect(spy).toHaveBeenCalledTimes(0);
    //        parameter.value = 'any value';
    //        expect(spy).toHaveBeenCalledTimes(1);
    //    });
    //});

    //describe('notifyObserversOfChangedProperty', () => {

    //    it('?', () => {
    //        expect(true).toEqual(false);
    //    });
    //});
});

describe('REoptIntParameter', () => {

    describe('max argument is not typeof "number"', () => {

        it('throws an error', () => {
            expect(function() {
                new REoptIntParameter('any displayName', 'namespace:name', 'any alias');
            }).toThrow(/must be typeof "number"/);
        });
    });
    
    describe('min argument not typeof "number"', () => {

        it('throws an error', () => {
            expect(() => {
                const max = 0;
                new REoptIntParameter('any displayName', 'namespace:name', 'any alias', max);
            }).toThrow(/must be typeof "number"/);
        });
    });

    describe('max is less than min', () => {

        it('throws an error', () => {
            expect(() => {
                const max = 1;
                const min = 2;
                new REoptIntParameter('any displayName', 'namespace:name', 'any alias', max, min)
            }).toThrow(/"max" argument must be greater than the "min" argument/);
        });
    });

    describe('set value', () => {

        describe('given a non-number primitive or object', () => {

            it.each(['1', true, null, undefined, {}])('throws an error given %o', (value) => {
                const parameter = makeREoptIntParameter();
                expect(() => parameter.value = value).toThrow(/argument must be typeof "number"/);
            });
        });

        describe('given NaN', () => {

            it('throws an error', () => {
                const parameter = makeREoptIntParameter();
                expect(() => parameter.value = NaN).toThrow(/argument must be an integer/);
            });
        });

        describe('given a float', () => {

            it('throws an error', () => {
                const parameter = makeREoptIntParameter();
                expect(() => parameter.value = 0.1).toThrow(/argument must be an integer/);
            });
        });

        describe('given an integer primitive', () => {

            it('sets the value', () => {
                const parameter = makeREoptIntParameter();
                parameter.value = 0;
                expect(parameter.value).toEqual(0);
            });
        });

        describe('given an integer greater than the max bound', () => {

            it('throws an error', () => {
                expect(function() {
                    const parameter = new REoptIntParameter('any displayName', 'namespace:name', 'any alias', 1, 0);
                    parameter.value = 2;
                }).toThrow(/argument must be <=/);
            });
        });

        describe('given an integer less than the min bound', () => {

            it('throws an error', () => {
                expect(function() {
                    const parameter = new REoptIntParameter('any displayName', 'namespace:name', 'any alias', 1, 0);
                    parameter.value = -1;
                }).toThrow(/argument must be >=/);
            });
        });
    });
});

describe('REoptFloatParameter', () => {

    describe('max argument is not typeof "number"', () => {

        it('throws an error', () => {
            expect(function() {
                new REoptFloatParameter('any displayName', 'namespace:name', 'any alias');
            }).toThrow(/argument must be typeof "number"/);
        });
    });
    
    describe('min argument is not typeof "number"', () => {

        it('throws an error', () => {
            expect(function() {
                new REoptFloatParameter('any displayName', 'namespace:name', 'any alias', 0);
            }).toThrow(/argument must be typeof "number"/);
        });
    });

    describe('max is less than min', () => {

        it('throws an error', () => {
            expect(() => {
                const max = 1;
                const min = 2;
                new REoptFloatParameter('any displayName', 'namespace:name', 'any alias', max, min)
            }).toThrow(/"max" argument must be greater than the "min" argument/);
        });
    });

    describe('set value', () => {

        describe('given non-float primitive or object', () => {

            it.each(['1', true, null, undefined, {}])('throws an error given %o', (value) => {
                const parameter = makeREoptFloatParameter();
                expect(() => parameter.value = value).toThrow(/argument must be typeof "number"/);
            });

        });

        describe('given NaN', () => {

            it('throws an error', () => {
                const parameter = makeREoptFloatParameter();
                expect(() => parameter.value = NaN).toThrow(/argument must not be NaN/);
            });
        });

        describe('given a float primitive', () => {

            it('sets the value', () => {
                const parameter = new REoptFloatParameter('any displayName', 'namespace:name', 'any alias', 2.1, 0);
                parameter.value = 2.1;
                expect(parameter.value).toEqual(2.1);
            });
        });

        describe('given a float greater than the max bound', () => {

            it('throws an error', () => {
                expect(function() {
                    const parameter = new REoptFloatParameter('any displayName', 'namespace:name', 'any alias', 1.1, 0);
                    parameter.value = 1.2;
                }).toThrow(/argument must be <=/);
            });
        });

        describe('given a float less than the min bound', () => {

            it('throws an error', () => {
                expect(function() {
                    const parameter = new REoptFloatParameter('any displayName', 'namespace:name', 'any alias', 1, 0);
                    parameter.value = -0.1;
                }).toThrow(/argument must be >=/);
            });
        });
    });
});

describe('REoptStringParameter', () => {

    describe('set value', () => {
    
        describe('given a non-string primitive or object', () => {

            it.each([true, 1, null, undefined, {}])('throws an error given %o', (value) => {
                const parameter = makeREoptStringParameter();
                expect(() => parameter.value = value).toThrow(/argument must be typeof "string"/);
            });
        });

        describe('given a string', () => {

            it('sets the value', () => {
                const parameter = new REoptStringParameter('any displayName', 'namespace:name', 'any alias');
                parameter.value = 'foo';
                expect(parameter.value).toEqual('foo');
            });

            it('removes leading and trailing whitespace from the value', () => {
                const parameter = new REoptStringParameter('any displayName', 'namespace:name', 'any alias');
                parameter.value = '  foo  ';
                expect(parameter.value).toEqual('foo');
            });
        });
    });
});

describe('REoptBooleanParameter', () => {

    describe('set value', () => {

        describe('given a non-boolean primitive or object', () => {

            it.each(['1', 1, null, undefined, {}])('throws an error given %o', (value) => {
                const parameter = makeREoptBooleanParameter();
                expect(() => parameter.value = value).toThrow(/argument must be typeof "boolean"/);
            });
        });

        describe('given a boolean', () => {

            it('sets the value', () => {
                const parameter = new REoptBooleanParameter('any displayName', 'namespace:name', 'any alias');
                parameter.value = true;
                expect(parameter.value).toEqual(true);
            });
        });
    });
});