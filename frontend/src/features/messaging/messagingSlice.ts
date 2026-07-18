import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface MessagingState {
  dmUnreadCount: number;
}

const initialState: MessagingState = {
  dmUnreadCount: 0,
};

const messagingSlice = createSlice({
  name: 'messaging',
  initialState,
  reducers: {
    setDMUnreadCount(state, action: PayloadAction<number>) {
      state.dmUnreadCount = action.payload;
    },
  },
});

export const { setDMUnreadCount } = messagingSlice.actions;
export default messagingSlice.reducer;
