import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getStorage } from "firebase/storage";

const firebaseConfig = {
  projectId: "routemaster-os",
  apiKey: "AIzaSyAQ5Ex7pJPrNW95WZLQD3ZgRQWDOF6pW0k",
  authDomain: "routemaster-os.firebaseapp.com",
  storageBucket: "routemaster-os.firebasestorage.app",
  messagingSenderId: "678543239034",
  appId: "1:678543239034:web:86465df83c4d71261c18c3"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);

export default app;
