import assert from "node:assert/strict";
import test from "node:test";
import { hasActionBar } from "../js/frontend.js";

for (const [version, expected] of [
    ["1.53.6", true], ["1.32.4", true], ["2.0.0", true], ["1.32.3", false], ["1.31.9", false],
    ["0.99.0", false], [undefined, false], ["", false], ["1.x", false],
]) {
    test(`action bar support for ${version}`, () => assert.equal(hasActionBar(version), expected));
}
