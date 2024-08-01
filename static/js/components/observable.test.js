import { describe, expect, it } from 'vitest'
import { Observable } from './observable.js';

// - https://stackoverflow.com/questions/243274/how-to-unit-test-abstract-classes-extend-with-stubs

function makeObservable() {
    return new Observable();
}

describe('Observable', () => {

    describe('registerObserver', () => {

        describe('given an object that is not instanceof Observer', () => {

            it('throws an error', () => {
                expect(() => makeObservable()).toThrow(/foo/);
            });
        });
    });
});