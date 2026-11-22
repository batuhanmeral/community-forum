import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { logout } from '@/features/auth/authSlice';

interface MessagingState {
  dmUnreadCount: number;
  modmailUnreadCount: number;
}

const initialState: MessagingState = {
  dmUnreadCount: 0,
  modmailUnreadCount: 0,
};

const messagingSlice = createSlice({
  name: 'messaging',
  initialState,
  reducers: {
    setDMUnreadCount(state, action: PayloadAction<number>) {
      state.dmUnreadCount = action.payload;
    },
    setModmailUnreadCount(state, action: PayloadAction<number>) {
      state.modmailUnreadCount = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder.addCase(logout, () => initialState);
  },
});

export const { setDMUnreadCount, setModmailUnreadCount } = messagingSlice.actions;
export default messagingSlice.reducer;
