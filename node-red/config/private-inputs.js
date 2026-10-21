"use strict";

const fs = require("fs");
const path = require("path");
const prefix = /^HOMELAB_NR_[A-Z0-9_]+$/;
const reference = /^\$\{(HOMELAB_NR_[A-Z0-9_]+)\}$/;

function references(value, result = new Set()) {
    if (typeof value === "string") {
        const match = reference.exec(value);
        if (match) result.add(match[1]);
    } else if (Array.isArray(value)) {
        for (const child of value) references(child, result);
    } else if (value && typeof value === "object") {
        for (const child of Object.values(value)) references(child, result);
    }
    return result;
}

function validate(values) {
    if (!values || Array.isArray(values) || typeof values !== "object") {
        throw new Error("Node-RED private inputs must be a JSON object");
    }
    for (const [key, value] of Object.entries(values)) {
        if (!prefix.test(key) || typeof value !== "string" || value.includes("\0")) {
            throw new Error("Invalid Node-RED private input name or type");
        }
    }
    return values;
}

function load({filePath, flowPath, settingKeys}, environment = process.env) {
    let values = {};
    try {
        values = validate(JSON.parse(fs.readFileSync(filePath, "utf8")));
    } catch (error) {
        if (error.code !== "ENOENT") {
            // Do not propagate JSON parser errors that could contain private values.
            throw new Error("Cannot read Node-RED private deployment inputs");
        }
    }
    const flows = JSON.parse(fs.readFileSync(flowPath, "utf8"));
    const required = references(flows);
    for (const key of settingKeys) {
        if (!prefix.test(key)) throw new Error("Invalid Node-RED setting input name");
        required.add(key);
    }
    const resolved = Object.create(null);
    for (const key of required) {
        const value = environment[key] === undefined ? values[key] : environment[key];
        if (typeof value !== "string" || value.length === 0 || value.includes("\0")) {
            throw new Error("Missing Node-RED private input: " + key);
        }
        resolved[key] = value;
    }
    // Validate every required value before changing this process's environment.
    for (const [key, value] of Object.entries(resolved)) environment[key] = value;
    return resolved;
}

// Node-RED 5 falls back to the flow directory if this file is absent. Never
// create or replace a credential store here: restore it through the private
// deployment workflow, using {} only for a deliberately new installation.
function requirePrivateCredentials(filePath = "/data/flows_cred.json") {
    try {
        const parent = fs.lstatSync(path.dirname(filePath));
        if (!parent.isDirectory() || parent.isSymbolicLink() || (parent.mode & 0o7777) !== 0o700) {
            throw new Error("Invalid private directory");
        }
        const stat = fs.lstatSync(filePath);
        if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o7777) !== 0o600) {
            throw new Error("Invalid private file");
        }
        const value = JSON.parse(fs.readFileSync(filePath, "utf8"));
        if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("Invalid JSON");
    } catch (_) {
        throw new Error("Restore the private Node-RED credential store before startup");
    }
    // Node-RED saves through a new temporary file followed by rename. Restrict
    // future writes as well as the existing store; do not chmod private inputs.
    process.umask(0o077);
}

module.exports = {load, references, validate, requirePrivateCredentials};
