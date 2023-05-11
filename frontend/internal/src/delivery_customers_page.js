import React from 'react';
import ReactDOM from 'react-dom';
import { DeliveryCustomersPage } from './pages/DeliveryCustomersPage.jsx';

ReactDOM.render(<DeliveryCustomersPage {...window.getPageProps()}/>, document.getElementById('root'));
