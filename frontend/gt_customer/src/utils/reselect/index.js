import { createSelector } from 'reselect';

const userInfoSelector = createSelector(
    (state) => state.user.info,
    (item) => item
);

export { userInfoSelector };
