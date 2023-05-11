import React, { useState, useEffect } from 'react';
import CustomSelect from '../CustomSelect/CustomSelectWithValues';

const CustomSelectWithStorage = ({
    localStorageService,
    updateData,
    options,
    values,
    defaultName,
    optionName = 'select',
}) => {
    const [mounted, setMounted] = useState(false);
    const [status, setStatus] = useState(localStorageService.get(optionName) || '');

    useEffect(() => {
        localStorageService.set(optionName, status);
        mounted && updateData();
    }, [status]);

    useEffect(() => {
        setMounted(true);
    }, []);

    return (
        <CustomSelect
            options={options}
            values={values}
            defaultName={defaultName}
            selected={status}
            onChange={(val) => setStatus(val)}
            defaultOption={options[0]}
        />
    );
};

export default CustomSelectWithStorage;
