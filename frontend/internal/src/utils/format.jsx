export function amountFormat(amount) {
    const int_value = Math.round(parseFloat(amount));
    const str_value = int_value.toString();

    return str_value.replace(/\B(?=(?:\d{3})+$)/g, '\u202F');
}
