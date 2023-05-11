import { storageService } from '../utils';
import { REQUESTS_PREFIX } from '../utils/constants';

function mapRequestList(list) {
    return list.map((r) => {
        const [firstItem] = r.items;

        return {
            ...r,
            index: firstItem.code,
            date: r.date,
            addresses: r.items.map((i) => ({
                ...i,
                index: i.code,
                id: i.id,
                text: i.address,
                interval: `${i.interval_begin}-${i.interval_end}`,
            })),
            pay_estimate: r.cost,
            mass: firstItem.mass,
            volume: firstItem.volume,
            max_size: firstItem.max_size,
            has_elevator:
                firstItem.has_elevator === null ? '-' : firstItem.has_elevator ? 'Есть' : 'Нет',
            elevators: r.items.map((el) =>
                el.has_elevator === null ? '-' : el.has_elevator ? 'Есть' : 'Нет'
            ),
            floor: firstItem.floor,
            carrying_distance: firstItem.carrying_distance,
            places: firstItem.place_count,
            executants: r.assigned_workers,
            contact: r.driver_name,
            phone: r.driver_phones,
            price: +r.cost,
            status: r.status,
        };
    });
}
const filterList = ({ list, filterStatus }) => {
    localStorageService.set('group', filterStatus);

    if (!filterStatus) {
        return list;
    }

    const lista = list.filter(({ status }) => {
        const a = DELIVERY_TABLE_FILTER_BY_STATUS.get(status.id) === filterStatus;
        console.log(a);
        return a;
    });
    console.log(lista);
    return lista;
};

function sortingList({ list, key, direction }) {
    localStorageService.set('sorting', { key, direction });
    if (list.length === 0) return list;
    return list.sort((prev, next) => {
        let prevKey, nextKey;
        switch (key) {
            case 'date':
                prevKey = prev[key].split('.').reverse().join('-');
                nextKey = next[key].split('.').reverse().join('-');
                break;
            case 'interval':
                prevKey = prev.addresses[0].interval;
                nextKey = next.addresses[0].interval;
                break;
            case 'route':
                prevKey = prev.addresses.length;
                nextKey = next.addresses.length;
                break;
            case 'status':
                prevKey = prev.status.order;
                nextKey = next.status.order;
                break;
            default:
                prevKey = prev[key];
                nextKey = next[key];
        }

        const value = direction === 'up' ? 1 : -1;
        return prevKey < nextKey ? value : -value;
    });
}

export const DELIVERY_DASHBOARD_GROUPS_NAMES = new Map([
    ['cancelled', ['removed', 'cancelled', 'failed', 'declined', 'cancelled_with_payment']],
    ['in_work', ['finished', 'partly_arrived', 'partly_photo_attached', 'photo_attached']],
    [
        'preprocessing',
        ['timepoint_confirmed', 'partly_confirmed', 'new', 'autotarification_attempt'],
    ],
    ['no_contact', ['no_response', 'driver_callback']],
]);

const getInitialGroup = (itemName) => {
    const groupMap = new Map();
    const currentGroupNames = DELIVERY_DASHBOARD_GROUPS_NAMES.get(itemName);

    if (!currentGroupNames) {
        return groupMap;
    }

    for (const groupTitle of currentGroupNames) {
        groupMap.set(groupTitle, { title: groupTitle, total: 0 });
    }

    return groupMap;
};

const getInitialItemState = (itemName) => ({
    groups: getInitialGroup(itemName),
    title: itemName,
    total: 0,
});

const getInitialRequestsDashboardState = (requests) => ({
    totalMoney: 0,
    total: requests.length,
    items: new Map([
        ['preprocessing', getInitialItemState('preprocessing')],
        ['in_work', getInitialItemState('in_work')],
        ['no_contact', getInitialItemState('no_contact')],
        ['cancelled', getInitialItemState('cancelled')],
    ]),
});

export const getMergedRequest = (request, prevRequests) => {
    const getRequestMap = (request) => {
        return new Map(request.map((request) => [request.pk, request]));
    };

    const requestMap = getRequestMap(request);
    const prevRequestsMap = getRequestMap(prevRequests);

    return [...new Map([...prevRequestsMap, ...requestMap]).values()];
};

export const DELIVERY_TABLE_FILTER_BY_STATUS = new Map([
    ['cancelled', 'cancelled'],
    ['cancelled_with_payment', 'cancelled'],
    ['declined', 'cancelled'],
    ['failed', 'cancelled'],
    ['removed', 'cancelled'],
    ['finished', 'in_work'],
    ['partly_arrival_submitted', 'in_work'],
    ['partly_arrived', 'in_work'],
    ['partly_photo_attached', 'in_work'],
    ['driver_callback', 'no_contact'],
    ['no_response', 'no_contact'],
    ['autotarification_attempt', 'preprocessing'],
    ['new', 'preprocessing'],
    ['partly_confirmed', 'preprocessing'],
    ['timepoint_confirmed', 'preprocessing'],
    ['photo_attached', 'in_work'],
]);
const getCurrentStatus = (stauts) => {
    switch (stauts) {
        case 'partly_arrival_submitted':
            return 'partly_arrived';
        default:
            return stauts;
    }
};

export const adapterDeliveryRequestsToDashboard = (requests, prevRequests) => {
    const currentRequest = prevRequests ? getMergedRequest(requests, prevRequests) : requests;

    return currentRequest.reduce((acc, { status, pay_estimate }) => {
        const currentStatus = getCurrentStatus(status.id);
        const itemName = DELIVERY_TABLE_FILTER_BY_STATUS.get(currentStatus);
        const curentItem = acc?.items.get(itemName) || getInitialItemState(itemName);

        const currentGroup = {
            total: (curentItem.groups.get(currentStatus)?.total || 0) + 1,
            title: currentStatus,
        };

        curentItem.groups.set(currentStatus, currentGroup);
        curentItem.total += 1;

        acc.items.set(itemName, curentItem);
        acc.totalMoney += Number(pay_estimate);

        return acc;
    }, getInitialRequestsDashboardState(requests));
};

const localStorageService = storageService(REQUESTS_PREFIX);

const requests = (
    state = {
        list: [],
        dashboard: getInitialRequestsDashboardState([]),
        isLoading: false,
        error: null,
        filterStatus: localStorageService.get('group', ''),
        sorting: localStorageService.get('sorting', { key: 'date', direction: 'up' }),
    },
    action
) => {
    switch (action.type) {
        case 'FETCH_REQUESTS_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_REQUESTS_SUCCESS': {
            const list = sortingList({
                list: mapRequestList(action.payload.data.requests),
                ...state.sorting,
            });

            return {
                ...state,
                isLoading: false,
                dashboard: adapterDeliveryRequestsToDashboard(list),
                list: filterList({ list, filterStatus: state.filterStatus }),
            };
        }
        case 'FETCH_REQUESTS_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };
        case 'UPDATE_REQUESTS_SORTING':
            return {
                ...state,
                sorting: action.payload.sorting,
                list: sortingList({ list: state.list, ...action.payload.sorting }),
            };
        case 'UPDATE_REQUESTS_FILTER':
            return {
                ...state,
                filterStatus: action.payload.filterStatus,
            };
        case 'UPDATE_REQUEST_SUCCESS':
            const newList = state.list.map((record) => {
                const { data } = action?.payload?.data;

                if (record?.pk === data?.pk) {
                    return data;
                }
                return record;
            });

            return {
                ...state,
                list: sortingList({ list: mapRequestList(newList), ...state.sorting }),
            };
        default:
            return state;
    }
};

export default requests;
