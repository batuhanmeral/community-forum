import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import notificationReducer from '@/features/notifications/notificationSlice';
import membershipsReducer from '@/features/communities/membershipsSlice';
import messagingReducer from '@/features/messaging/messagingSlice';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    notifications: notificationReducer,
    messaging: messagingReducer,
    memberships: membershipsReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
