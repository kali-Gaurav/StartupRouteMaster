/// <reference types="vite/client" />
// Telegram WebApp API Type Definitions
interface TelegramWebAppUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  added_to_attachment_menu?: boolean;
}

interface TelegramWebAppInitData {
  user?: TelegramWebAppUser;
  receiver?: TelegramWebAppUser;
  chat?: {
    id: number;
    type: string;
    title?: string;
    username?: string;
    photo_url?: string;
  };
  auth_date: number;
  hash: string;
  start_param?: string;
  can_send_after?: number;
  chat_instance?: string;
  chat_type?: string;
}

interface TelegramWebApp {
  ready: () => void;
  expand: () => void;
  close: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
  sendData: (data: string) => void;
  switchInlineQuery: (query: string, chat_types?: string[]) => void;
  openLink: (url: string, options?: { try_instant_view?: boolean }) => void;
  openTelegramLink: (url: string) => void;
  openInvoice: (url: string, callback?: (status: string) => void) => void;
  showPopup: (params: {
    title?: string;
    message: string;
    buttons?: Array<{
      id?: string;
      type?: string;
      text: string;
    }>;
  }, callback?: (button_id: string) => void) => void;
  showAlert: (message: string, callback?: () => void) => void;
  showConfirm: (message: string, callback?: (confirmed: boolean) => void) => void;
  requestWriteAccess: (callback?: (success: boolean) => void) => void;
  requestContactAccess: (callback?: (success: boolean) => void) => void;
  requestPhoneAccess: (callback?: (success: boolean) => void) => void;
  readTextFromClipboard: (callback?: (text: string | null) => void) => void;
  writeTextToClipboard: (text: string, callback?: () => void) => void;
  isVersionAtLeast: (version: string) => boolean;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  isClosingConfirmationEnabled: boolean;
  headerColor: string;
  backgroundColor: string;
  bottomBarColor?: string;
  initDataUnsafe: TelegramWebAppInitData;
  initData: string;
  version: string;
  platform: string;
  colorScheme: string;
  themeParams: {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
    secondary_bg_color?: string;
  };
  isIframe: boolean;
  onViewportChanged?: (callback: () => void) => void;
  offViewportChanged?: (callback: () => void) => void;
  onThemeChanged?: (callback: () => void) => void;
  offThemeChanged?: (callback: () => void) => void;
  onClipboardTextReceived?: (callback: (text: string | null) => void) => void;
  offClipboardTextReceived?: (callback: (text: string | null) => void) => void;
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp;
  };
}