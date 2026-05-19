import { initializeApp } from "firebase/app"
import { getFirestore } from "firebase/firestore"

const firebaseConfig = {
  apiKey: "AIzaSyD8R094x5ZSGVxDfeyEnf1NU1QVmtjfiEc",
  authDomain: "react-test-542ec.firebaseapp.com",
  projectId: "react-test-542ec",
  storageBucket: "react-test-542ec.firebasestorage.app",
  messagingSenderId: "799537066214",
  appId: "1:799537066214:web:a2a218695183c1c8424b27"
}

const app = initializeApp(firebaseConfig)

export const db = getFirestore(app)