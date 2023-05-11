let tempList = [
    {
        number: '0-0032',
        date: '25.05.2020',
        period: '17.02.2020 - 17.03.2020',
        sum: 1435,
        deadline: '25.06.2020',
        status: 'Новая',
        timesheet_photos: [],
    },
];

tempList = tempList
    .concat(tempList)
    .concat(tempList)
    .concat(tempList)
    .concat(tempList)
    .concat(tempList)
    .concat(tempList)
    .concat(tempList)
    .concat(tempList)
    .concat(tempList);

const codeToText = {
    new: 'Новая',
    confirmed: 'Согласована',
    in_payment: 'В оплате',
    paid: 'Оплачена',
};

const reports = (state = { list: [], isLoading: false, error: null }, action) => {
    switch (action.type) {
        case 'FETCH_REPORTS_REQUEST':
            return { ...state, isLoading: true };
        case 'FETCH_REPORTS_SUCCESS':
            return {
                ...state,
                isLoading: false,
                list: action.payload.data.map((r) => ({
                    pk: r.pk,
                    account_date: r.account_date,
                    account_number: r.account_number,
                    number: r.number,
                    date: r.creation_date,
                    location: r.location,
                    period: `${r.first_day} - ${r.last_day}`,
                    sum: +r.amount,
                    scans: r.scans,
                    deadline: r.deadline,
                    status: codeToText[r.status],
                })),
            };
        case 'FETCH_REPORTS_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };

        case 'CONFIRM_REPORTS_REQUEST':
            return { ...state, isLoading: true };
        case 'CONFIRM_REPORTS_SUCCESS':
            return {
                ...state,
                isLoading: false,
                list: state.list.map((r) =>
                    r.pk === action.payload.data.pk ? action.payload.data : r
                ),
            };
        case 'CONFIRM_REPORTS_FAILURE':
            return { ...state, isLoading: false, error: action.error.response.message };

        default:
            return state;
    }
};

export default reports;
