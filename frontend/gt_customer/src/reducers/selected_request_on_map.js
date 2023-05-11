const selected_request_on_map = (state = { id: -1, request_type: 'all' }, action) => {
    switch (action.type) {
        case 'SET_SELECTED_MAP_REQUEST':
            return { ...state, id: action.id };
        case 'SET_SELECTED_MAP_REQUEST_TYPE':
            return { ...state, request_type: action.request_type };
        default:
            return state;
    }
};

export default selected_request_on_map;
