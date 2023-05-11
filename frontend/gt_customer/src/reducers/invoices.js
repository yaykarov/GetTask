const invoices = (state = { list: [], isLoading: false, error: null }, action) => {
    switch (action.type) {
        case 'FETCH_INVOICES_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_INVOICES_SUCCESS':
            return { ...state, isLoading: false, list: action.payload.data };
        case 'FETCH_INVOICES_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };

        default:
            return state;
    }
};

export default invoices;
