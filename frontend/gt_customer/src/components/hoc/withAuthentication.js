import React from 'react';
import Authentication from '../Authentication/Authentication';

const withAuthentication = (Wrapped) => {
    return (props) => (
        <Authentication {...props}>{(newProps) => <Wrapped {...newProps} />}</Authentication>
    );
};

export default withAuthentication;
