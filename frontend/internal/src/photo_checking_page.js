import React from 'react';
import ReactDOM from 'react-dom';
import { PhotoCheckingPage } from './pages/PhotoCheckingPage.jsx';

ReactDOM.render(<PhotoCheckingPage {...window.getPageProps()}/>, document.getElementById('root'));
