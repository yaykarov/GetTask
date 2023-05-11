import Editable from '../../Editable/Editable';
import CustomSelectWithValues from '../../CustomSelect/CustomSelectWithValues';
import React from 'react';
import { AddressSuggestions } from 'react-dadata';
import { DADATA_API_KEY } from '../../../utils/constants';
import styles from './RequestsPage.module.scss';

const Elevator =
    ({ updateData, options, selected, values }) =>
    (value, setValue, handleSubmit, onBlur, setOpened) => {
        return (
            <CustomSelectWithValues
                onChange={(p) => {
                    if (p !== '') {
                        handleSubmit(p);
                    }
                    onBlur();
                }}
                setOpened={setOpened}
                selected={selected}
                options={options}
                values={values}
                updateData={updateData}
                optionName={'has_elevator'}
                dontShowDefaultNameInOptions
            />
        );
    };

const options = [
    {
        title: 'Неизвестно',
        value: null,
    },
    {
        title: 'Есть',
        value: true,
    },
    {
        title: 'Нет',
        value: false,
    },
];

export const elevatorEditor = ({ elem, c, updateData, itemPk }) => {
    return (
        <Editable
            inputComponent={Elevator({
                selected: elem.items[0][c],
                options: options.map((e) => e.title),
                values: options.map((e) => e.value),
                updateData,
            })}
            field={'has_elevator'}
            pk={elem.pk}
            item_pk={itemPk}
            text={elem[c]}
            editable={elem.status.id === 'autotarification_attempt'}
        />
    );
};

export const expandedElevatorEditor = ({ elem, addr, c, updateData, index }) => {
    return (
        <Editable
            inputComponent={Elevator({
                selected: addr[c],
                options: options.map((e) => e.title),
                values: options.map((e) => e.value),
                updateData,
            })}
            field={'has_elevator'}
            pk={elem.pk}
            item_pk={addr.id}
            text={elem.elevators[index]}
            editable={elem.status.id === 'autotarification_attempt'}
        />
    );
};

export const AddressesEditor = ({ elem, addr }) => (
    <Editable
        inputComponent={(value, setValue, handleSubmit) => (
            <AddressSuggestions
                inputProps={{
                    autoFocus: true,
                }}
                defaultQuery={addr.text}
                token={DADATA_API_KEY}
                value={value}
                onChange={(addr) => {
                    setValue(addr);
                    handleSubmit(addr.value);
                }}
                containerClassName={styles.addressSuggestions}
            />
        )}
        field={'address'}
        pk={elem.pk}
        item_pk={addr.id}
        text={addr.text}
        editable={elem.status.id === 'autotarification_attempt'}
    />
);
