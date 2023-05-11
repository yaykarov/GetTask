const default_map_data = {
    timestamp: undefined,
    delivery_requests: [],
    workers: [],
    bounding_box: undefined,
    city_borders: undefined,
};

const default_state = {
    mapData: default_map_data,
    delivery_requests_autocomplete: undefined,
};

const requests_on_map = (state = default_state, action) => {
    switch (action.type) {
        case 'FETCH_REQUESTS_ON_MAP_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_REQUESTS_ON_MAP_SUCCESS':
            return { ...state, isLoading: false, mapData: action.payload.data };
        case 'FETCH_REQUESTS_ON_MAP_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };

        case 'FETCH_REQUESTS_ON_MAP_REQUEST_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_REQUESTS_ON_MAP_AUTOCOMPLETE_SUCCESS':
            return { ...state, delivery_requests_autocomplete: action.payload.data };
        case 'FETCH_REQUESTS_ON_MAP_AUTOCOMPLETE_FAILURE':
            return { ...state, isLoading: false, delivery_requests_autocomplete: [] };

        default:
            return state;
    }
};

export default requests_on_map;
