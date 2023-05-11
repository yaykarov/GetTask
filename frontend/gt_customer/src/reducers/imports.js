const imports = (state = { list: [], isLoading: false, error: null }, action) => {
    switch (action.type) {
        case 'FETCH_IMPORTS_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_IMPORTS_SUCCESS':
            return {
                ...state,
                isLoading: false,
                list: action.payload.data.map((r) => ({
                    date: r.timepoint,
                    file: r.imported_file,
                    report: r.report,
                    status: r.status,
                })),
            };
        case 'FETCH_IMPORTS_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };

        default:
            return state;
    }
};

export default imports;
