import React from 'react';
import ReactDOM from 'react-dom';
import PaymentSchedule from './pages/PaymentSchedule.jsx';

ReactDOM.render(<PaymentSchedule {...window.getPSProps()}/>, document.getElementById('ps_root'));
