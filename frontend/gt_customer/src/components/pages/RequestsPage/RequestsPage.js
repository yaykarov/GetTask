import React, { memo, useCallback, useEffect, useState } from 'react';
import { connect } from 'react-redux';
import { Redirect } from 'react-router-dom';
import { bindActionCreators } from 'redux';
import _ from 'underscore';
import Popup from 'reactjs-popup';
import styled from 'styled-components';
import moment from 'moment';
import {
    fetchRequests,
    moveItem,
    removeItem,
    copyItem,
    cancelRequest,
    removeRequest,
    fetchLocation,
    updateAddressOptions,
    setSorting,
    setFilter,
    updateRequest,
} from '../../../actions';
import styles from './RequestsPage.module.scss';
import Pagination from '../../Pagination/Pagination';
import CustomAutocomplete from '../../CustomAutocomplete/CustomAutocomplete';
import NewRequestPopup from '../../NewRequestPopup/NewRequestPopup';
import PhotoTooltip from '../../PhotoTooltip/PhotoTooltip';
import Editable from '../../Editable/Editable';
import PopupInfo from '../../PopupInfo/PopupInfo';
import { AddressSuggestions } from 'react-dadata';
import {
    DADATA_API_KEY,
    BACKEND_URL,
    ITEMS_ON_PAGE,
    REQUESTS_PREFIX,
} from '../../../utils/constants';
import PopupModal from '../../PopupModal/PopupModal';
import DatePickerApply from '../../DatePickerApply/DatePickerApply';
import { storageService } from '../../../utils';
import { userInfoSelector } from '../../../utils/reselect';
import { DownloadExcelButton, ImportsButton } from '../../buttons';
import { ViewButton } from '../../buttons';
import ButtonsContainer from '../../ButtonsContainer/ButtonsContainer';
import Wrapper from '../../Wrapper/Wrapper';
import CustomSelectWithStorage from '../../CustomSelectWithStorage/CustomSelectWithStorage';
import SearchWrapper from '../../SearchWrapper/SearchWrapper';
import Dashboard from '../../Dashboard/Dashboard';
import TableRequestsWrapper from '../../TableRequestsWrapper/TableRequestsWrapper';
import { AddressesEditor, elevatorEditor, expandedElevatorEditor } from './editors';
const LongPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
    &-overlay {
        position: fixed !important;
        height: 100vh !important;
        overflow-y: auto;
    }
`;

const ShortPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

function currencyFormat(num) {
    return num.toFixed(2).replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ');
}

const localStorageService = storageService(REQUESTS_PREFIX);

function ButtonApprove({ updateRequest, pk, value, style }) {
    return (
        <div className={styles.buttonsContainer2} style={style}>
            <div
                onClick={() => {
                    updateRequest(undefined, {
                        request: pk,
                        customer_confirmation: value,
                        force_commit: false,
                    });
                }}
                className={styles.approveButton}
            >
                {value ? (
                    <>
                        <img alt='icon' src='/check_icon.svg' />
                        <div>&nbsp;Согласовать</div>
                    </>
                ) : (
                    <div>x</div>
                )}
            </div>
        </div>
    );
}

function ExpandedCellRoutePart({
    elem,
    setModalPopup,
    moveItem,
    copyItem,
    removeItem,
    updateRequests,
    addr,
}) {
    return (
        <>
            <img
                className={styles.tableButton}
                style={{ opacity: 0, cursor: 'default' }}
                alt='icon'
                src='/add_icon2.svg'
            />
            <div style={{ opacity: 0, cursor: 'default' }} className={styles.tableExpandButton}>
                {elem.addresses.length}
            </div>
            <img
                onClick={() => {
                    setModalPopup({
                        open: true,
                        title: 'Вынести адрес в отдельную заявку?',
                        onOk: () =>
                            moveItem({ item_pk: addr.pk, target_pk: null }).then(updateRequests),
                    });
                }}
                style={elem.status.id === 'new' ? {} : { opacity: 0, cursor: 'default' }}
                title={'Вынести в отдельную заявку'}
                className={styles.tableButton}
                alt='icon'
                src='/minus_icon.svg'
            />
            <img
                onClick={() => {
                    setModalPopup({
                        open: true,
                        title: 'Дублировать адрес в отдельную заявку?',
                        onOk: () => copyItem({ item_pk: addr.pk }).then(updateRequests),
                    });
                }}
                style={elem.status.id === 'new' ? {} : { opacity: 0, cursor: 'default' }}
                title={'Дублировать в отдельную заявку'}
                className={styles.tableButton}
                alt='icon'
                src='/copy_icon.svg'
            />
            <img
                onClick={() => {
                    setModalPopup({
                        open: true,
                        title: 'Удалить адрес?',
                        onOk: () => removeItem({ item_pk: addr.pk }).then(updateRequests),
                    });
                }}
                style={elem.status.id === 'new' ? {} : { opacity: 0, cursor: 'default' }}
                title={'Удалить'}
                className={styles.tableButton}
                alt='icon'
                src='/delete_icon.svg'
            />
        </>
    );
}

function RequestsPage({
    list,
    dashboard,
    isLoading,
    sorting,
    filterStatus,
    setSorting,
    fetchRequests,
    moveItem,
    removeItem,
    copyItem,
    userInfo,
    removeRequest,
    fetchLocation,
    updateAddressOptions,
    updateRequest,
}) {
    const { allow_requests_creation } = userInfo;
    const [itemsOnPage, setItemsOnPage] = useState(
        localStorageService.get('itemsOnPage', ITEMS_ON_PAGE)
    );
    const [branch, setBranch] = useState([]);

    const [columns, setColumns] = useState({
        pk: { text: '№', isVisible: false, style: { maxWidth: '120px' } },
        date: { text: 'Дата', isVisible: true, style: { maxWidth: '120px' } },
        index: { text: 'Индекс', isVisible: true, style: { maxWidth: '120px' } },
        route: { text: 'Маршрут', isVisible: true, style: { maxWidth: 'none' } },
        addresses: { text: 'Адрес', isVisible: true, style: { maxWidth: '300px' } },
        shipment_type: { text: 'Груз', isVisible: false, style: { maxWidth: '120px' } },
        mass: { text: 'Масса', isVisible: true, style: { maxWidth: 'none' } },
        volume: { text: 'Объем', isVisible: true, style: { maxWidth: 'none' } },
        max_size: { text: 'Г-т', isVisible: true, style: { maxWidth: 'none' } },
        has_elevator: { text: 'Лифт', isVisible: true, style: { maxWidth: 'none' } },
        floor: { text: 'Этаж', isVisible: true, style: { maxWidth: 'none' } },
        carrying_distance: { text: 'Пронос', isVisible: true, style: { maxWidth: 'none' } },
        places: { text: 'Мест', isVisible: true, style: { maxWidth: 'none' } },
        interval: { text: 'Интервал', isVisible: true, style: { maxWidth: '120px' } },
        confirmed_timepoint: { text: 'Сог-е время', isVisible: true, style: { maxWidth: '120px' } },
        arrival_time: { text: 'Время начала', isVisible: true, style: { maxWidth: '120px' } },
        executants: { text: 'Исп-лей', isVisible: true, style: { maxWidth: '120px' } },
        contact: { text: 'Контактное лицо', isVisible: true, style: { maxWidth: 'none' } },
        phone: { text: 'Телефон', isVisible: true, style: { maxWidth: '150px' } },
        price: { text: 'Стоимость', isVisible: true, style: { maxWidth: '120px' } },
        hours: { text: 'Часы', isVisible: true, style: { maxWidth: '120px' } },
        approve: { text: 'Согласовать', isVisible: true, style: { maxWidth: '240px' } },
        status: { text: 'Статус', isVisible: true, style: { maxWidth: 'none' } },
        comment: { text: 'Комментарий', isVisible: true, style: { maxWidth: '240px' } },
        customer_comment: {
            text: 'Комментарий клиента',
            isVisible: true,
            style: { maxWidth: '240px' },
        },
    });

    const [expandedRow, setExpandedRow] = useState([]);
    const [page, setPage] = useState(1);
    const pages = Math.ceil(list.length / itemsOnPage);
    const [addressPopupOpenedId, setAddressPopupOpenedId] = useState(-1);
    const [addressPopupInput, setAddressPopupInput] = useState('');
    const [addressId, setAddressId] = useState(-1);
    const [addressOptions, setAddressOptions] = useState([]);
    const [requestPopup, setRequestPopup] = useState({ open: false, route: null, disable: null });
    const [tooltipContentHover, setTooltipContentHover] = useState(false);
    const [tooltipOpen, setTooltipOpen] = useState(false);
    const [tooltipTriggerHover, setTooltipTriggerHover] = useState(false);
    const [tooltipElement, setTooltipElement] = useState(null);
    const [tooltipImgUrls, setTooltipImgUrls] = useState(null);
    const [infoPopup, setInfoPopup] = useState({ open: false, content: '' });
    const [modalPopup, setModalPopup] = useState({ open: false, content: '' });

    const customerResolution = [
        { title: 'Согласована', value: 'confirmed' },
        { title: 'На рассмотрении', value: 'normal' },
        { title: 'Подозрительная', value: 'suspicious' },
    ];

    const statusInfo = {
        autotarification_attempt: {
            title: 'Тарифицируется',
            class: 'status-autotarification_attempt',
        },
        new: { title: 'Новая', class: 'status-new', show: true },
        timepoint_confirmed: { title: 'Поиск исполнителя', class: 'status-timepoint_confirmed' },
        partly_confirmed: { title: 'Назначен', class: 'status-partly_confirmed' },

        partly_arrived: { title: 'В пути', class: 'status-partly_arrived' },
        partly_photo_attached: { title: 'На месте', class: 'status-partly_photo_attached' },
        photo_attached: { title: 'Проверка табеля', class: 'status-photo_attached' },
        finished: { title: 'Выполнена', class: 'status-finished' },

        no_response: { title: 'Нет ответа', class: 'status-no_response' },
        driver_callback: { title: 'Перезвонит сам', class: 'status-driver_callback' },

        declined: { title: 'Не принята', class: 'status-declined' },
        cancelled: { title: 'Отмена', class: 'status-cancelled' },
        removed: { title: 'Удалена', class: 'status-removed', show: true },
        failed: { title: 'Срыв заявки', class: 'status-failed', show: true },
        cancelled_with_payment: {
            title: 'Отмена с оплатой',
            class: 'status-cancelled_with_payment',
        },
    };

    const filterMap = (filter) => {
        switch (filter) {
            case 'Несогласованные заявки':
                return 'active';
            case 'Заявки в оплате':
                return 'in_payment';
            case 'Оплаченные заявки':
                return 'paid';
            default:
                return null;
        }
    };
    const statusAllowCancel = [
        'driver_callback',
        'no_response',
        'partly_confirmed',
        'partly_arrived',
        'partly_photo_attached',
        'photo_attached',
    ];

    function getStatusClass(status) {
        let statusClass = 'status-default';

        if (statusInfo.hasOwnProperty(status.id)) statusClass = statusInfo[status.id].class;

        return styles.status + ' ' + styles[statusClass];
    }

    function calculateTop() {
        let scrollHeight = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight,
            document.body.clientHeight,
            document.documentElement.clientHeight
        );
        return Math.min(
            tooltipElement && tooltipElement.getBoundingClientRect().top + window.pageYOffset,
            scrollHeight - 520
        );
    }

    function _updateAddressOptions() {
        updateAddressOptions({
            q: addressPopupInput,
            forward: JSON.stringify({
                request: addressPopupOpenedId,
            }),
        }).then((res) =>
            setAddressOptions(res.payload.data.results.map((r) => ({ text: r.text, id: +r.id })))
        );
    }

    function toggleExpandAll() {
        expandedRow.length ? setExpandedRow([]) : setExpandedRow(list.map((item) => item.pk));
    }

    function toggleExpandedRow(i) {
        const idx = expandedRow.indexOf(i);
        if (idx === -1) {
            setExpandedRow([...expandedRow, i]);
        } else {
            setExpandedRow([...expandedRow.slice(0, idx), ...expandedRow.slice(idx + 1)]);
        }
    }

    const updateRequests = useCallback(() => {
        fetchLocation({
            forward: JSON.stringify({
                first_day: moment(localStorageService.get('startRanges')).format('DD.MM.YYYY'),
                last_day: moment(localStorageService.get('endRanges')).format('DD.MM.YYYY'),
            }),
        }).then((res) =>
            setBranch(res.payload.data.results.map((r) => ({ id: +r.id, text: r.text })))
        );

        return fetchRequests({
            search_text: localStorageService.get('search'),
            payment_status: filterMap(localStorageService.get('filter')),
            status: localStorageService.get('status'),
            customer_resolution: localStorageService.get('customer_resolution'),
            location: localStorageService.get('branch'),
            first_day: moment(localStorageService.get('startRanges')).format('DD.MM.YYYY'),
            last_day: moment(localStorageService.get('endRanges')).format('DD.MM.YYYY'),
        });
    }, []);

    function changeSorting(key) {
        let { direction } = sorting;

        if (sorting.key === key) {
            direction = direction === 'down' ? 'up' : 'down';
        }

        setSorting({ key, direction });
    }

    let updateData = _.throttle(updateRequests, 500);
    let updateAddressOptions_t = _.throttle(_updateAddressOptions, 500);

    useEffect(() => {
        setAddressPopupInput('');
        setAddressId(-1);
    }, [addressPopupOpenedId]);

    useEffect(() => {
        if (addressPopupOpenedId !== -1) {
            updateAddressOptions_t();
        }
    }, [addressPopupInput, addressPopupOpenedId]);

    useEffect(() => {
        localStorageService.set('itemsOnPage', itemsOnPage);
    }, [itemsOnPage]);
    useEffect(() => {
        updateRequests();
    }, [filterStatus]);

    function expandedCellPart(elem, c) {
        if (expandedRow.indexOf(elem.pk) === -1) {
            return null;
        }
        return elem.addresses.slice(1).map((addr, index) => {
            const renderExpandedCellPart = () => {
                const isEditable = elem.status.id !== 'new';

                switch (c) {
                    case 'route':
                        return (
                            <ExpandedCellRoutePart
                                elem={elem}
                                addr={addr}
                                setModalPopup={setModalPopup}
                                copyItem={copyItem}
                                moveItem={moveItem}
                                removeItem={removeItem}
                                updateRequests={updateRequests}
                            />
                        );

                    case 'addresses':
                        return AddressesEditor({ elem, addr });

                    case 'has_elevator':
                        return expandedElevatorEditor({
                            elem,
                            c,
                            updateData,
                            index: index + 1,
                            addr,
                        });

                    case 'places':
                        return (
                            <Editable
                                field={'place_count'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr.place_count}
                                editable={isEditable}
                            />
                        );

                    case 'max_size':
                        return (
                            <Editable
                                field={'max_size'}
                                pk={elem.pk}
                                item_pk={elem.addresses[index + 1].id}
                                text={elem.addresses[index + 1][c]}
                                editable={isEditable}
                            />
                        );

                    case 'index':
                        return (
                            <Editable
                                field={'code'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr[c]}
                                editable={isEditable}
                            />
                        );
                    case 'interval':
                        return (
                            <Editable
                                field={'time_interval'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr[c]}
                                editable={isEditable}
                            />
                        );

                    case 'mass':
                        return (
                            <Editable
                                field={'mass'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr[c].toString().replace(/\./gi, ',')}
                                editable={isEditable}
                            />
                        );

                    case 'volume':
                        return (
                            <Editable
                                field={'volume'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr[c].toString().replace(/\./gi, ',')}
                                editable={isEditable}
                            />
                        );

                    case 'floor':
                        return (
                            <Editable
                                field={'floor'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr[c]}
                                editable={isEditable}
                            />
                        );

                    case 'carrying_distance':
                        return (
                            <Editable
                                field={'carrying_distance'}
                                pk={elem.pk}
                                item_pk={elem.addresses[index + 1].id}
                                text={elem.addresses[index + 1][c]}
                                editable={isEditable}
                            />
                        );

                    case 'place_count':
                        return (
                            <Editable
                                field={'place_count'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr.place_count}
                                editable={isEditable}
                            />
                        );

                    case 'shipment_type':
                        return (
                            <Editable
                                field={'shipment_type'}
                                pk={elem.pk}
                                item_pk={addr.id}
                                text={addr.shipment_type}
                                editable={isEditable}
                            />
                        );
                    default:
                        return addr[c];
                }
            };
            return (
                <div className={c === 'route' ? styles.tableImgWrapper : ''} key={addr.id}>
                    {renderExpandedCellPart()}
                </div>
            );
        });
    }

    function mainCellPart(elem, c) {
        const isEditable = elem.status.id !== 'new';

        if (c === 'route') {
            if (elem.status.id === 'autotarification_attempt') {
                return (
                    <div
                        className={styles.tableExpandButton}
                        style={{ display: elem.addresses.length > 1 ? 'block' : 'none' }}
                        onClick={() => toggleExpandedRow(elem.pk)}
                    >
                        {elem.addresses.length}
                    </div>
                );
            } else {
                return (
                    <>
                        <img
                            className={styles.tableButton}
                            onClick={() => {
                                const req = list.find((r) => r.pk === elem.pk);

                                setRequestPopup({
                                    open: true,
                                    route: {
                                        routeId: elem.pk,
                                        date: req.date,
                                        driver: req.contact,
                                        phones: req.phone,
                                    },
                                    disable: ['route'],
                                });
                            }}
                            title='Добавить в маршрут'
                            alt='icon'
                            src='/add_icon2.svg'
                        />
                        <div
                            className={styles.tableExpandButton}
                            style={{ display: elem.addresses.length > 1 ? 'block' : 'none' }}
                            onClick={() => toggleExpandedRow(elem.pk)}
                        >
                            {elem.addresses.length}
                        </div>
                    </>
                );
            }
        }
        if (c === 'addresses') {
            return (
                <Editable
                    inputComponent={(value, setValue, handleSubmit) => (
                        <AddressSuggestions
                            inputProps={{ autoFocus: true }}
                            defaultQuery={elem.addresses[0].text}
                            token={DADATA_API_KEY}
                            value={value}
                            onChange={(addr) => {
                                setValue(addr.value);
                                handleSubmit(addr.value);
                            }}
                            containerClassName={styles.addressSuggestions}
                        />
                    )}
                    field={'address'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem.addresses[0].text}
                    editable={isEditable}
                />
            );
        }
        if (c === 'mass') {
            return (
                <Editable
                    field={'mass'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem.mass.toString().replace(/\./gi, ',')}
                    editable={isEditable}
                />
            );
        }
        if (c === 'volume') {
            return (
                <Editable
                    field={'volume'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem.volume.toString().replace(/\./gi, ',')}
                    editable={isEditable}
                />
            );
        }
        if (c === 'has_elevator') {
            return elevatorEditor({ elem, c, updateData, itemPk: elem.addresses[0].id, index: 0 });
        }
        if (c === 'floor') {
            return (
                <Editable
                    field={'floor'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem[c]}
                    editable={isEditable}
                />
            );
        }
        if (c === 'max_size') {
            return (
                <Editable
                    field={'max_size'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem[c]}
                    editable={isEditable}
                />
            );
        }
        if (c === 'carrying_distance') {
            return (
                <Editable
                    field={'carrying_distance'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem[c]}
                    editable={isEditable}
                />
            );
        }
        if (c === 'interval') {
            return (
                <Editable
                    field={'time_interval'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem.addresses[0].interval}
                    editable={isEditable}
                />
            );
        }
        if (c === 'index') {
            return (
                <>
                    <Editable
                        field={'code'}
                        pk={elem.pk}
                        item_pk={elem.addresses[0].id}
                        text={elem[c]}
                        editable={isEditable}
                    />
                    <div
                        style={{
                            width: 19,
                            minWidth: 19,
                            marginLeft: 10,
                            display: 'flex',
                            justifyContent: 'center',
                        }}
                    >
                        <img
                            alt={elem.customer_resolution}
                            src={`/customer_resolution_${elem.customer_resolution}.svg`}
                        />
                    </div>
                </>
            );
        }
        if (c === 'places') {
            return (
                <Editable
                    field={'place_count'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem[c]}
                    editable={isEditable}
                />
            );
        }
        if (c === 'shipment_type') {
            return (
                <Editable
                    field={'shipment_type'}
                    pk={elem.pk}
                    item_pk={elem.addresses[0].id}
                    text={elem.addresses[0].shipment_type}
                    editable={isEditable}
                />
            );
        }
        if (c === 'date') {
            return (
                <Editable
                    field={'date'}
                    pk={elem.pk}
                    item_pk={null}
                    text={moment(elem[c]).format('DD.MM.YYYY')}
                    editable={isEditable}
                />
            );
        }

        if (c === 'contact') {
            return (
                <Editable
                    field={'driver_name'}
                    pk={elem.pk}
                    item_pk={null}
                    text={elem[c]}
                    editable={isEditable}
                />
            );
        }
        if (c === 'phone') {
            return (
                <Editable
                    field={'driver_phones'}
                    pk={elem.pk}
                    item_pk={null}
                    text={elem[c].join(' ')}
                    editable={isEditable}
                />
            );
        }
        if (c === 'comment') {
            return (
                <Editable field={'comment'} pk={elem.pk} item_pk={null} text={elem[c]} editable />
            );
        }

        if (c === 'arrival_time') {
            return elem[c] ? moment(elem[c]).format('HH:mm') : null;
        }

        if (c === 'customer_comment') {
            return (
                <Editable
                    field={'customer_comment'}
                    pk={elem.pk}
                    item_pk={null}
                    text={elem[c]}
                    editable={false}
                />
            );
        }
        if (c === 'hours') {
            return (
                <Editable
                    field={'customer_comment'}
                    pk={elem.pk}
                    item_pk={null}
                    text={elem.worked_hours}
                    editable={isEditable}
                />
            );
        }
        if (c === 'price') {
            return currencyFormat(elem.price);
        }
        if (c === 'status') {
            return elem.status.text;
        }

        if (c === 'approve') {
            const isVisible =
                elem.status.id === 'finished' || elem.status.id === 'cancelled_with_payment';

            const renderButtonApprove = (value) => {
                return (
                    <ButtonApprove
                        pk={elem.pk}
                        value={value}
                        updateRequest={updateRequest}
                        updateRequests={updateRequests}
                    />
                );
            };

            if (elem.customer_resolution !== 'confirmed' && isVisible) {
                return renderButtonApprove(true);
            } else if (elem.customer_resolution === 'confirmed' && isVisible) {
                return renderButtonApprove(false);
            } else {
                return null;
            }
        }

        return elem[c];
    }

    function tableCell(elem, c) {
        let className = null;

        if (c === 'route') {
            className = styles.tableImgWrapper;
        }

        if (c?.toString() === 'status') {
            className = getStatusClass(elem[c]);
        }

        return (
            <td key={c} style={columns[c].style} className={styles.tableBody_td}>
                <div
                    className={`${className} ${styles.tableBodyDiv} ${styles.tableBody_td_item}`}
                    style={{
                        overflow: c === 'addresses' ? 'visible' : '',
                        ...(c === 'index'
                            ? { display: 'flex', justifyContent: 'space-between' }
                            : {}),
                    }}
                >
                    {mainCellPart(elem, c)}
                </div>
                {expandedCellPart(elem, c)}
            </td>
        );
    }

    function tableRow(elem) {
        let cells = [];
        cells.push(
            <td
                className={`${styles.photoPopup} ${styles.tableBody_td} ${styles.tableBody_td_img}`}
                key={`button1_${elem.index}`}
            >
                <img
                    className={`${styles.tablePhotoIcon} ${styles.tableBody_td_img_item} ${
                        elem?.finish_photos?.length ? '' : styles.disabled
                    }`}
                    alt='icon'
                    src='/photo_icon.svg'
                    onMouseEnter={(e) => {
                        if (elem.finish_photos.length) {
                            e.persist();
                            setTooltipTriggerHover(true);
                            setTooltipElement(e.target);
                            setTooltipImgUrls([...elem.finish_photos, ...elem.start_photos]);
                        }
                    }}
                    onMouseLeave={(e) => {
                        if (elem.finish_photos.length) {
                            e.persist();
                            setTooltipTriggerHover(false);
                            setTooltipElement(e.target);
                            setTooltipOpen(true);
                            setTimeout(() => setTooltipOpen(false), 500);
                        }
                    }}
                />
            </td>
        );

        cells.push(
            ...Object.keys(columns)
                .filter((c) => columns[c].isVisible)
                .map((c) => tableCell(elem, c))
        );

        cells.push(
            <td key={`button2_${elem.index}`} className={styles.tableBody_td}>
                {elem.status.id === 'new' ? (
                    <img
                        className={styles.tableButton2}
                        alt='icon'
                        src='/delete_circle_icon.svg'
                        onClick={() => {
                            removeRequest({ pk: elem.pk })
                                .then(() =>
                                    setInfoPopup({
                                        open: true,
                                        title: 'Заявка удалена',
                                        content: '',
                                    })
                                )
                                .then(updateRequests)
                                .catch((err) =>
                                    setInfoPopup({
                                        open: true,
                                        content:
                                            err.error.response.data.message ||
                                            `${err.error.response.status} ${err.error.response.statusText}`,
                                        title: 'Ошибка',
                                    })
                                );
                        }}
                    />
                ) : statusAllowCancel.indexOf(elem.status.id) !== -1 ? (
                    <img
                        className={styles.tableButton2}
                        alt='icon'
                        src='/cancel_icon.svg'
                        onClick={() => {
                            setInfoPopup({
                                open: true,
                                title: 'Отмена заявки',
                                content: `Для отмены заявки №${elem.pk} обратитесь к диспетчеру по телефону +7 (969) 777-13-56`,
                            });
                        }}
                    />
                ) : null}
            </td>
        );

        return (
            <tr
                key={elem.index}
                className={[
                    styles.requestTable,
                    styles.tableBody_tr,
                    elem.customer_resolution === 'suspicious' ? styles.trSuspicious : '',
                    elem.customer_resolution === 'confirmed' ? styles.trConfirmed : '',
                ].join(' ')}
            >
                {cells}
            </tr>
        );
    }

    function tableBody() {
        return list
            .slice(itemsOnPage * (page - 1), itemsOnPage * page)
            .map((elem) => tableRow(elem));
    }

    return (
        <Wrapper title='Заявки'>
            <Dashboard data={dashboard} filterStatus={filterStatus} setFilter={setFilter} />

            <SearchWrapper
                placeHolder='Найти заявку'
                localStorageService={localStorageService}
                updateData={updateData}
                itemsOnPage={itemsOnPage}
                setItemsOnPage={setItemsOnPage}
            >
                <ViewButton columns={columns} setColumns={setColumns} />
            </SearchWrapper>
            <ButtonsContainer
                left={
                    <>
                        <DatePickerApply
                            localStorageService={localStorageService}
                            defaultRangeStart={moment().toDate()}
                            updateData={updateData}
                        />
                        <CustomSelectWithStorage
                            options={Object.keys(statusInfo).map((item) => statusInfo[item].title)}
                            values={Object.keys(statusInfo)}
                            defaultName='Статус заявки'
                            localStorageService={localStorageService}
                            updateData={updateData}
                            optionName='status'
                        />
                        <CustomSelectWithStorage
                            options={customerResolution.map((item) => item.title)}
                            values={customerResolution.map((item) => item.value)}
                            defaultName='Резолюция'
                            localStorageService={localStorageService}
                            updateData={updateData}
                            optionName='customer_resolution'
                        />
                        <CustomSelectWithStorage
                            options={[
                                'Несогласованные заявки',
                                'Заявки в оплате',
                                'Оплаченные заявки',
                            ]}
                            defaultName='Тип заявок'
                            localStorageService={localStorageService}
                            updateData={updateData}
                            optionName='filter'
                        />
                        {userInfo.show_locations_filter && (
                            <CustomSelectWithStorage
                                options={branch.map((item) => item.text)}
                                values={branch.map((item) => item.id)}
                                defaultName='Филиал'
                                localStorageService={localStorageService}
                                updateData={updateData}
                                optionName='branch'
                            />
                        )}
                    </>
                }
                right={
                    <>
                        <LongPopup
                            open={requestPopup.open}
                            onClose={() =>
                                setRequestPopup({ open: false, route: null, disable: null })
                            }
                            modal
                            forceRender
                            closeOnDocumentClick
                        >
                            {(close) => (
                                <NewRequestPopup
                                    close={close}
                                    route={requestPopup.route}
                                    disableList={requestPopup.disable}
                                    onSuccess={updateRequests}
                                />
                            )}
                        </LongPopup>
                        <div
                            onClick={() => {
                                if (allow_requests_creation) {
                                    setRequestPopup({ open: true, route: null, disable: null });
                                } else {
                                    setInfoPopup({
                                        open: true,
                                        content: 'Пополните баланс для подачи заявок',
                                        title: 'Недостаточно средств',
                                    });
                                }
                            }}
                            className={styles.buttonsContainerItem}
                        >
                            <img
                                alt='icon'
                                src='/add_icon.svg'
                                className={styles.buttonsContainerIcon1}
                            />
                        </div>
                        <ImportsButton
                            allow_requests_creation={allow_requests_creation}
                            updateData={updateData}
                        />
                        <DownloadExcelButton />
                    </>
                }
            />

            <TableRequestsWrapper
                isLoading={isLoading}
                head={
                    <tr className={styles.tableHead}>
                        <td></td>
                        {Object.keys(columns)
                            .filter((c) => columns[c].isVisible)
                            .map((c) => {
                                let img_link = '/sort_' + sorting.direction + '_icon.svg';
                                return (
                                    <td key={c} style={columns[c].style}>
                                        <div
                                            style={{ display: 'flex' }}
                                            className={styles.tableHeadTd}
                                        >
                                            {c === 'route' ? (
                                                <img
                                                    onClick={toggleExpandAll}
                                                    style={{ marginRight: '5px' }}
                                                    src='/expand_icon.svg'
                                                />
                                            ) : null}
                                            <div
                                                onClick={() => changeSorting(c)}
                                                style={{ display: 'flex' }}
                                            >
                                                {columns[c].text}
                                                {sorting.key == c ? <img src={img_link} /> : null}
                                            </div>
                                        </div>
                                    </td>
                                );
                            })}
                        <td></td>
                    </tr>
                }
                body={tableBody()}
                pagination={
                    <Pagination
                        stylesRef={{
                            wrap: { margin: 0, width: 'auto' },
                            item: { fontSize: '12px', width: '28px', height: '28px' },
                        }}
                        pages={pages}
                        onPageChange={(p) => setPage(p)}
                    />
                }
            />
            <ShortPopup
                modal
                closeOnDocumentClick
                open={infoPopup.open}
                onClose={() => setInfoPopup({ ...infoPopup, open: false })}
            >
                {(close) => (
                    <PopupInfo title={infoPopup.title} close={close}>
                        <div dangerouslySetInnerHTML={{ __html: infoPopup.content }}></div>
                    </PopupInfo>
                )}
            </ShortPopup>
            <ShortPopup
                modal
                closeOnDocumentClick
                open={modalPopup.open}
                onClose={() => setModalPopup({ ...modalPopup, open: false })}
            >
                {(close) => (
                    <PopupModal
                        title={modalPopup.title}
                        close={close}
                        onOk={modalPopup.onOk}
                        onCancel={modalPopup.onCancel}
                    >
                        {modalPopup.content}
                    </PopupModal>
                )}
            </ShortPopup>
            <div
                onMouseEnter={() => setTooltipContentHover(true)}
                onMouseLeave={() => setTooltipContentHover(false)}
                className={styles.tooltipWrapper}
                style={{
                    display:
                        tooltipContentHover || tooltipTriggerHover || tooltipOpen
                            ? 'block'
                            : 'none',
                    top: calculateTop(),
                    left: 350,
                }}
            >
                <PhotoTooltip urls={tooltipImgUrls} title='Фото' />
            </div>
        </Wrapper>
    );
}

const mapStateToProps = (state) => ({
    list: state.requests.list,
    dashboard: state.requests.dashboard,
    sorting: state.requests.sorting,
    filterStatus: state.requests.filterStatus,
    isLoading: state.requests.isLoading,
    userInfo: userInfoSelector(state),
});

const mapDispatchToProps = (dispatch) =>
    bindActionCreators(
        {
            fetchRequests,
            moveItem,
            removeItem,
            copyItem,
            cancelRequest,
            removeRequest,
            fetchLocation,
            updateAddressOptions,
            setSorting,
            updateRequest,
        },
        dispatch
    );

export default connect(mapStateToProps, mapDispatchToProps)(memo(RequestsPage));
