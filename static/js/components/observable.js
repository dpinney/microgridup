export { Observable, Observer };

/*
interface Observable {
    +registerObserver
    +removeObserver
    +notifyObserversOfChangedProperty
}
*/
class Observable {

    #observers;

    constructor() {
        if (this.constructor === Observable) {
            throw Error('Cannot instantiate abstract class "Observable".');
        }
        this.#observers = [];
    }

    get observers() {
        return this.#observers;
    }

    set observers(observers) {
        throw Error('readonly accessor descriptor');
    }

    /**
     * @param {Observer} observer
     */
    registerObserver(observer) {
        this.#observers.push(observer);
    } 

    /**
     * @param {Observer} observer
     */
    removeObserver(observer) {
        const index = this.#observers.indexOf(observer);
        if (index > -1) {
            this.#observers.splice(index, 1);
        }
    }

    removeObservers() {
        this.#observers = [];
    }

    notifyObserversOfChangedProperty(id, oldValue) {
        throw Error('Cannot call abstract method notifyObserversOfChangedProperty');
    }
}

/*
interface Observer {
    +handleChangedProperty
}
*/
class Observer {
    // - Remember: an interface is just an abstract class with NO implementation or state!
    // - JavaScript doesn't have multiple inheritance. Is it worth using mixins? Since this is just an interface, the answer is no. Mixins are
    //   complicated and the complication won't help me

    constructor() {
        if (this.constructor === Observer) {
            throw Error('Cannot instantiate abstract class "Observer".');
        }
    }

    /**
     * @param {object} observable
     * @param {string} property
     * @param {object} oldVavlue
     * @returns {undefined}
     */
    handleChangedProperty(reoptParameters, id, oldValue) {
        throw Error('Cannot call abstract method "handleChangedProperty".');
    }
}