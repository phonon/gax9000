
// https://stackoverflow.com/questions/175739/how-can-i-check-if-a-string-is-a-valid-number
export function isNumeric(val) {
    if ( typeof val !== "number" && typeof val !== "string" ) return false; // only numbers and strings
    return !isNaN(val) && // use type coercion to parse the _entirety_ of the string (`parseFloat` alone does not do this)...
           !isNaN(parseFloat(val)); // ...and ensure strings of whitespace fail
}

/**
 * Return if value is a number and not NaN.
 */
export function isValidNumber(val) {
    return (typeof val === "number") && !isNaN(val);
}