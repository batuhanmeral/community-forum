import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { logout } from '@/features/auth/authSlice';

interface NotificationState {
  unreadCount: number;
}

const initialState: NotificationState = {
  unreadCount: 0,
};

const notificationSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    setUnreadCount(state, action: PayloadAction<number>) {
      state.unreadCount = action.payload;
    },
    decrementUnread(state) {
      state.unreadCount = Math.max(0, state.unreadCount - 1);
    },
    clearUnread(state) {
      state.unreadCount = 0;
    },
  },
  extraReducers: (builder) => {
    builder.addCase(logout, () => initialState);
  },
});

export const { setUnreadCount, decrementUnread, clearUnread } = notificationSlice.actions;
export default notificationSlice.reducer;
