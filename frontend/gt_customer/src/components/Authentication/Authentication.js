import React, { useState } from 'react';
import Popup from 'reactjs-popup';
import styled from 'styled-components';
import styles from './Authentication.module.scss';
import PopupInfo from '../PopupInfo/PopupInfo';
import { bindActionCreators } from 'redux';
import { accountInfo, obtainToken, resetPassword, updatePassword, signup } from '../../actions';
import { connect } from 'react-redux';
import { Redirect, withRouter } from 'react-router-dom';
import { getToken } from '../../utils';

const StyledPopup = styled(Popup)`
    &-content {
        width: inherit !important;
        border-radius: 6px;
        padding: 0 !important;
    }
`;

const getFrom = (location, user) => {
    if (user.info.registrationStatus === 'info_required') {
        return { pathname: '/info' };
    }
    if (location) {
        return location.state.from;
    }

    return { pathname: '/' };
};

const Authentication = (props) => {
    const { location, children, user } = props;
    const [popup, setPopup] = useState({ open: false, content: '', title: '' });

    if (user.token) {
        return <Redirect to={getFrom(location, user)} />;
    }

    return (
        <div className={styles.wrapper}>
            <StyledPopup
                modal
                closeOnDocumentClick
                open={popup.open}
                onClose={() => setPopup({ ...popup, open: false })}
            >
                {(close) => (
                    <PopupInfo title={popup.title} close={close}>
                        {popup.content}
                    </PopupInfo>
                )}
            </StyledPopup>
            <img alt='logo' src='/logo.svg' className={styles.logo} />
            <div className={styles.container}>{children({ ...props, setPopup, popup })}</div>
            <div className={styles.bottom}>
                <img alt='icon' src='/facebook_icon.svg' className={styles.icon} />
                <img alt='icon' src='/linkedin_icon.svg' />
                <div className={styles.copyright}>GetTask © 2022</div>
            </div>
        </div>
    );
};

const mapStateToProps = (state) => ({ user: state.user });

const mapDispatchToProps = (dispatch) =>
    bindActionCreators(
        { accountInfo, obtainToken, resetPassword, updatePassword, signup },
        dispatch
    );

export default connect(mapStateToProps, mapDispatchToProps)(withRouter(Authentication));
