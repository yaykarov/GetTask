import React from 'react';
import ReactDOM from 'react-dom';
import { ContractsList } from './pages/ContractsList.jsx';

ReactDOM.render(<ContractsList {...window.getPageProps()}/>, document.getElementById('root'));
