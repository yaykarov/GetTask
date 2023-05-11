import React, { useEffect, useState } from 'react';
import { connect } from 'react-redux';
import { bindActionCreators } from 'redux';
import Popup from 'reactjs-popup';
import { Calendar } from 'react-date-range';
import { AddressSuggestions } from 'react-dadata';
import 'react-dadata/dist/react-dadata.css';
import styles from './NewRequestPopup.module.scss';
import CustomAutocomplete from '../CustomAutocomplete/CustomAutocomplete';
import styled from 'styled-components';
import moment from 'moment';
import * as locales from 'react-date-range/dist/locale';
import { createRequest, addAddressToRequest } from '../../actions';
import TimePicker from '../TimePicker/TimePicker';
import PopupInfo from '../PopupInfo/PopupInfo';
import { DADATA_API_KEY, BACKEND_URL } from '../../utils/constants';
import { Button, Checkbox, Form, Input } from 'antd';
import { useForm } from 'antd/lib/form/Form';
import axios from 'axios';
import { getToken } from '../../utils';

const ShortPopup = styled(Popup)`
    &-content {
        flex: 0 0 0 !important;
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const formatDate = (date) => (date ? moment(date).format('DD.MM.YYYY') : '');

const Label = ({ children, required }) => {
    return (
        <div required={required} className={styles.label}>
            {children}
        </div>
    );
};

const transformToPossibleDisabledItem = (WrappedComponent, name, disableList, disablePropName = 'disable') => (props) => {
    const isDisabled = disableList ? disableList.includes(name) : false;

    return <WrappedComponent {...props} {...{[disablePropName]: isDisabled}}/>
}

const FormItemDependentOnRoute = ({ routeId, label, name, ...props }) => {
    const changeValueDependentOnRoute = (value) => {
        if (routeId === -1) {
            return { value };
        }

        return { value: '' };
    };

    return (
        <Form.Item
            label={<Label>{label}</Label>}
            name={name}
            getValueProps={changeValueDependentOnRoute}
        >
            <Input
                disabled={routeId !== -1}
                className={`${routeId !== -1 ? styles.disabled : ''} ${styles.form_input}`}
                {...props}
            />
        </Form.Item>
    );
};

const DateViewer = ({ date, openPopup, routeId }) => {
    const formattedData = formatDate(date);
    const isExistRoute = routeId !== -1;
    const classNames = `${styles.datePicker} ${isExistRoute ? styles.disabled : ''}`;

    const onOpenPopup = () => {
        if (!isExistRoute) {
            openPopup(true);
        }
    };

    if (date) {
        return (
            <div onClick={onOpenPopup} className={classNames}>
                <div>{formattedData}</div>
            </div>
        );
    }

    return <div onClick={onOpenPopup} className={classNames}></div>;
};

const createAddresOrRequest = async ({
    routeId,
    value,
    date,
    time,
    addAddressToRequest,
    createRequest,
}) => {
    const [intervalBegin, intervalEnd] = time;
    const formattedVolume = Number(value.volume.replace(',', '.'));
    const isExistRoute = routeId !== -1;

    const {
        index,
        mass,
        places,
        shipment_type,
        address,
        has_elevator,
        driver,
        phones,
        workers_required,
        max_size = null,
        floor = null,
        carrying_distance = null,
    } = value;

    if (isExistRoute) {
        await addAddressToRequest(
            {},
            {
                request: routeId,
                interval_begin: intervalBegin,
                interval_end: intervalEnd,
                code: index,
                mass,
                volume: formattedVolume,
                place_count: places,
                shipment_type,
                address: address.value,
                has_elevator,
                max_size,
                floor,
                carrying_distance,
            }
        );
    } else {
        await createRequest(
            {},
            {
                location: null,
                driver_name: driver,
                driver_phones: phones,
                date,
                items: [
                    {
                        mass,
                        shipment_type,
                        has_elevator,
                        workers_required,
                        code: index,
                        place_count: places,
                        interval_begin: intervalBegin,
                        interval_end: intervalEnd,
                        address: address.value,
                        volume: formattedVolume,
                        carrying_distance,
                        floor,
                        max_size,
                    },
                ],
            }
        );
    }
};

function calcHeight(value) {
    let numberOfLineBreaks = (value.match(/\n/g) || []).length;
    // * min-height + lines x line-height + padding + border
    let newHeight = 20 + numberOfLineBreaks * 20 + 12 + 2;
    return newHeight;
}

const requiredList = [
    'index',
    'date',
    'time',
    'volume',
    'mass',
    'places',
    'workers_required',
    'shipment_type',
    'address',
];

const fieldsNameList = {
    'Планируемая дата': 'date',
    'Индекс груза': 'index',
    'Общий вес, кг': 'mass',
    'Объем, м3': 'volume',
    'Кол-во мест': 'places',
    'Характер груза': 'shipment_type',
    'Адрес забора/доставки': 'address',
    'Временной интервал': 'time',
    Водитель: 'driver',
    'Телефон водителя': 'phones',
};

function NewRequestPopup({ close, addAddressToRequest, createRequest, route, onSuccess, disableList }) {
    const [form] = useForm();
    const [fields, setFields] = useState([
        { name: 'time', value: [null, null] },
        { name: 'has_elevator', value: true },
        { name: 'date', value: route?.date && moment(route.date, 'YYYY.MM.DD').toDate() },
    ]);

    const [routeOptions, setRouteOptions] = useState([]);
    const [fullText, setFullText] = useState('');
    const [routeId, setRouteId] = useState(route ? route.routeId : -1);
    const [datePopupOpened, setDatePopupOpened] = useState(false);
    const [infoPopup, setInfoPopup] = useState({ open: false, content: '' });

    const date = form.getFieldValue('date');
    const routeSearch = form.getFieldValue('route');

    const checkIsNotValidate = () => {
        const requiredValues = form.getFieldsValue(requiredList);
        const formattedValues = Object.entries(Object.values(requiredValues));
        const errorValues = form.getFieldsError(requiredList);

        for (const [index, value] of formattedValues) {
            if (!value) {
                return true;
            }

            if (errorValues[index].errors.length) {
                return true;
            }
        }
    };

    const setFieldData = (name, value) => {
        const isExistRoute = routeId !== -1;
        let formattedValue = value;

        switch (name) {
            case 'address':
                formattedValue = {
                    value,
                };
                break;

            case 'date':
                formattedValue = moment(value, 'DD.MM.YYYY').toDate();
                break;

            case 'time': {
                formattedValue = value.split('-');
                break;
            }
        }

        if (name === 'date' && isExistRoute) {
            return;
        }

        form.setFields([{ name, value: formattedValue }]);
    };

    const onAutoFillForm = (value) => {
        const getDataRegex = /^([а-я ,-/\d]+): ([\d\w\.:-а-я/, ]+)/i;
        const formattedValue = value.replace(/"/g, '');

        const lines = formattedValue.split('\n').map((line) => {
            const [, key, value] = line.match(getDataRegex) || [];
            return [key, value];
        });

        for (const [key, value] of lines) {
            const fieldName = fieldsNameList[key];

            if (fieldName) {
                setFieldData(fieldName, value);
            }
        }
    };
    useEffect(() => {
        updateRouteOptions();
    }, [routeSearch, date]);

    //TODO: переделать на общий запрос из экшиона
    const updateRouteOptions = async () => {
        if (!date) return;

        const { data } = await axios({
            method: 'get',
            url: `${BACKEND_URL}gt/customer/request_autocomplete`,
            params: {
                q: routeSearch,
                forward: JSON.stringify({
                    date: formatDate(date),
                }),
            },
            headers: {
                Authorization: `Bearer ${getToken()}`,
            },
        });

        setRouteOptions(data.results.map((r) => ({ text: r.text, id: +r.id })));
    };

    const submitForm = async (value) => {
        try {
            const time = form.getFieldValue('time') || [];

            await createAddresOrRequest({
                routeId,
                value,
                date: formatDate(date),
                time,
                addAddressToRequest,
                createRequest,
            });

            setInfoPopup({
                open: true,
                content: 'Заявка успешно создана',
                title: 'Результат',
            });

            onSuccess();
        } catch (err) {
            setInfoPopup({
                open: true,
                content:
                    err.error.response.data.message ||
                    `${err.error.response.status} ${err.error.response.statusText}`,
                title: 'Ошибка',
            });
        }
    };

    const requiredRule = [{ required: true, message: '' }];

    const PossibleDisableCustomAutocomplete = transformToPossibleDisabledItem(CustomAutocomplete, 'route', disableList, 'disabled')

    return (
        <div className={styles.viewPopup}>
            <div onClick={close} className={styles.viewPopupClose}>
                <img alt='icon' src='/close_icon.svg' />
            </div>

            <div className={styles.viewPopupTitle}>Новая заявка</div>
            <Label>Весь текст заявки</Label>
            <Popup
                trigger={
                    <textarea
                        className={styles.form_textarea}
                        onPaste={(e) => {
                            const data = e.clipboardData.getData('Text');
                            onAutoFillForm(data);
                            setFullText(data);

                            e.target.style.height =
                                calcHeight(e.clipboardData.getData('Text')) + 'px';
                        }}
                        onChange={() => ''}
                        value={fullText}
                        rows='12'
                    />
                }
                position='bottom center'
                on='hover'
            >
                <span className={styles.textareaTooltip}>
                    {'В это поле можно вставить текст в формате\n' +
                        '"Планируемая дата: 06.07.2020\n' +
                        'Индекс груза: МИРЧТХ-11/277\n' +
                        'Общий вес, кг: 134\n' +
                        'Объем, м3: 1,55\n' +
                        'Кол-во мест: 10\n' +
                        'Характер груза: ЛИЧНЫЕ ВЕЩИ\n' +
                        'Адрес забора/доставки: Москва Неманский проезд 7к1\n' +
                        'Временной интервал: 09:00-18:00\n' +
                        'Водитель: ВЕМЯЕВ АНАТОЛИЙ НИКОЛАЕВИЧ\n' +
                        'Телефон водителя: 89653676747", и все поля заполнятся автоматически.'}
                </span>
            </Popup>

            <Form
                className={styles.container}
                form={form}
                fields={fields}
                onFieldsChange={(_, allFields) => {
                    setFields(allFields);
                }}
                onFinish={submitForm}
            >
                <Form.Item>
                    <div className={styles.form_row_3}>
                        <Form.Item label={<Label required>Дата</Label>}>
                            <ShortPopup
                                open={datePopupOpened}
                                onClose={() => setDatePopupOpened(false)}
                                modal
                                closeOnDocumentClick
                            >
                                {(close) => (
                                    <Form.Item
                                        name='date'
                                        valuePropName='date'
                                        rules={requiredRule}
                                    >
                                        <Calendar
                                            onChange={() => {
                                                close();
                                            }}
                                            locale={locales['ru']}
                                            color='#000000'
                                            rangeColors={['#000000']}
                                        />
                                    </Form.Item>
                                )}
                            </ShortPopup>

                            <DateViewer
                                date={date}
                                openPopup={setDatePopupOpened}
                                routeId={routeId}
                            />
                        </Form.Item>

                        <Form.Item label={<Label required>Время</Label>}>
                            <ShortPopup 

                                trigger={() => {
                                    const [intervalBegin, intervalEnd] =
                                        form.getFieldValue('time') || [];

                                    if (intervalBegin && intervalEnd) {
                                        return (
                                            <div className={styles.datePicker}>
                                                <div>{`${intervalBegin}-${intervalEnd}`}</div>
                                            </div>
                                        );
                                    }

                                    return <div className={styles.datePicker}></div>;
                                }}
                                modal
                                closeOnDocumentClick
                            >
                                {(close) => (
                                    <Form.Item name='time' rules={requiredRule}>
                                        <TimePicker close={close} />
                                    </Form.Item>
                                )}
                            </ShortPopup>
                        </Form.Item>

                        <Form.Item
                            label={<Label required>Индекс</Label>}
                            rules={requiredRule}
                            name='index'
                        >
                            <Input className={styles.form_input} />
                        </Form.Item>
                    </div>
                </Form.Item>

                <Form.Item
                    label={<Label>Прикрепить к маршруту</Label>}
                    style={{ marginBottom: 8 }}
                    name='route'
                >
                    <PossibleDisableCustomAutocomplete
                        options={routeOptions}
                        onIdChange={setRouteId}
                        defaultId={route?.routeId || -1}
                    />
                </Form.Item>

                <Form.Item>
                    <div className={styles.form_row_4}>
                        <Form.Item
                            label={<Label required>Объем</Label>}
                            name='volume'
                            rules={requiredRule}
                        >
                            <Input className={styles.form_input} />
                        </Form.Item>

                        <Form.Item
                            label={<Label required>Масса</Label>}
                            name='mass'
                            rules={requiredRule}
                        >
                            <Input className={styles.form_input} />
                        </Form.Item>

                        <Form.Item
                            label={<Label required>Кол-во мест</Label>}
                            name='places'
                            rules={requiredRule}
                        >
                            <Input className={styles.form_input} />
                        </Form.Item>

                        <Form.Item
                            label={<Label required>Грузчиков</Label>}
                            name='workers_required'
                            rules={requiredRule}
                        >
                            <Input className={styles.form_input} />
                        </Form.Item>
                    </div>
                </Form.Item>

                <Form.Item>
                    <div className={styles.form_row_4}>
                        <Form.Item label={<Label>М. габарит</Label>} name='max_size'>
                            <Input className={styles.form_input} />
                        </Form.Item>

                        <Form.Item label={<Label>Этаж</Label>} name='floor'>
                            <Input className={styles.form_input} />
                        </Form.Item>

                        <Form.Item label={<Label>Пронос</Label>} name='carrying_distance'>
                            <Input className={styles.form_input} />
                        </Form.Item>

                        <Form.Item
                            label={<Label>Лифт</Label>}
                            name='has_elevator'
                            valuePropName='checked'
                        >
                            <Checkbox className={styles.form_checkbox} type='checkbox' />
                        </Form.Item>
                    </div>
                </Form.Item>

                <Form.Item
                    label={<Label required>Характер груза</Label>}
                    name='shipment_type'
                    rules={requiredRule}
                >
                    <Input className={styles.form_input} />
                </Form.Item>

                <Form.Item
                    label={<Label required>Адрес</Label>}
                    name='address'
                    rules={requiredRule}
                >
                    <AddressSuggestions
                        defaultQuery={route?.address}
                        token={DADATA_API_KEY}
                        containerClassName={styles.addressSuggestions}
                    />
                </Form.Item>

                <FormItemDependentOnRoute label='ФИО водителя' name='driver' routeId={routeId} />

                <FormItemDependentOnRoute
                    label='Телефоны водителя'
                    name='phones'
                    routeId={routeId}
                />

                <Form.Item>
                    <Button
                        htmlType='submit'
                        className={`${styles.button} ${
                            checkIsNotValidate() ? styles.disabled : ''
                        }`}
                    >
                        Создать новую заявку
                    </Button>
                </Form.Item>
            </Form>

            <ShortPopup
                modal
                closeOnDocumentClick
                open={infoPopup.open}
                onClose={() => {
                    if (infoPopup.title === 'Результат') {
                        close();
                    } else {
                        setInfoPopup({ ...infoPopup, open: false });
                    }
                }}
            >
                {(close) => (
                    <PopupInfo title={infoPopup.title} close={close}>
                        {infoPopup.content}
                    </PopupInfo>
                )}
            </ShortPopup>
        </div>
    );
}

const mapStateToProps = (state) => ({
    user: state.user,
});

const mapDispatchToProps = (dispatch) =>
    bindActionCreators({ createRequest, addAddressToRequest }, dispatch);

export default connect(mapStateToProps, mapDispatchToProps)(NewRequestPopup);
