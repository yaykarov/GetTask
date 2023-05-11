import React from 'react';
import ReactDOM from 'react-dom';
import App from './pages/Expenses.jsx';

ReactDOM.render(<App {...window.getAppProps()}/>, document.getElementById('root'));
