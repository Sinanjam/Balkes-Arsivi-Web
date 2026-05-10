import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import { getAuth, signInAnonymously } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js";
import {
  getFirestore,
  collection,
  addDoc,
  getDocs,
  query,
  where,
  serverTimestamp
} from "https://www.gstatic.com/firebasejs/10.12.5/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyCQ7HB7pmQ_mODZIjAVaM9JC_4deMMO1iI",
  authDomain: "balkes-arsivi.firebaseapp.com",
  projectId: "balkes-arsivi",
  storageBucket: "balkes-arsivi.firebasestorage.app",
  messagingSenderId: "746095156584"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

const PLACEHOLDER = "assets-sizden-gelenler.svg";

function text(v){
  return String(v || "").trim();
}

function asMillis(v){
  if (!v) return 0;
  if (typeof v.toMillis === "function") return v.toMillis();
  if (typeof v.seconds === "number") return v.seconds * 1000;
  return 0;
}

function submissionToItem(docSnap){
  const d = docSnap.data() || {};
  const body = text(d.body);
  const title = text(d.title) || "Sizden Gelenler";
  const author = text(d.authorName);
  const sourceLine = author ? `Gönderen: ${author}` : "Sizden Gelenler";

  return {
    id: "submission-" + docSnap.id,
    title,
    summary: body.length > 260 ? body.slice(0, 260).trim() + "…" : body,
    paragraphs: author ? [sourceLine, body] : [body],
    content: body,
    photos: [{
      asset: PLACEHOLDER,
      caption: "Temsilidir"
    }],
    tables: [],
    imageCount: 1,
    tableCount: 0,
    archiveName: "Sizden Gelenler",
    sourceType: "submission",
    createdAtMillis: asMillis(d.createdAt)
  };
}

async function ensureUser(){
  if (auth.currentUser) return auth.currentUser;
  const result = await signInAnonymously(auth);
  return result.user;
}

async function loadApprovedSubmissions(){
  try {
    const q = query(collection(db, "submissions"), where("status", "==", "approved"));
    const snap = await getDocs(q);
    const items = snap.docs
      .map(submissionToItem)
      .sort((a, b) => (b.createdAtMillis || 0) - (a.createdAtMillis || 0));

    if (window.BALKES_ADD_DYNAMIC_ITEMS) {
      window.BALKES_ADD_DYNAMIC_ITEMS(items);
    }
  } catch (err) {
    console.warn("Sizden Gelenler yüklenemedi:", err);
  }
}

function openModal(){
  const modal = document.getElementById("submit-modal");
  if (!modal) return;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeModal(){
  const modal = document.getElementById("submit-modal");
  if (!modal) return;
  modal.hidden = true;
  document.body.style.overflow = "";
}

function setStatus(msg, isError = false){
  const el = document.getElementById("submit-status");
  if (!el) return;
  el.textContent = msg || "";
  el.classList.toggle("error", !!isError);
}

async function submitForm(ev){
  ev.preventDefault();

  const title = text(document.getElementById("sg-title")?.value);
  const body = text(document.getElementById("sg-body")?.value);
  const authorName = text(document.getElementById("sg-author")?.value);

  if (title.length < 3) {
    setStatus("Başlık en az 3 karakter olmalı.", true);
    return;
  }

  if (body.length < 10) {
    setStatus("Yazı en az 10 karakter olmalı.", true);
    return;
  }

  try {
    setStatus("Gönderiliyor...");
    const user = await ensureUser();

    await addDoc(collection(db, "submissions"), {
      title,
      body,
      authorName,
      photoPath: "",
      photoUrl: "",
      status: "pending",
      uid: user.uid,
      createdAt: serverTimestamp(),
      appVersion: "web",
      versionCode: 0,
      platform: "web"
    });

    ev.target.reset();
    setStatus("Gönderiniz alındı. Onaylandıktan sonra yayınlanacaktır.");
  } catch (err) {
    console.error(err);
    setStatus("Gönderi alınamadı. Daha sonra tekrar deneyin.", true);
  }
}

document.getElementById("open-submit")?.addEventListener("click", openModal);
document.getElementById("close-submit")?.addEventListener("click", closeModal);
document.getElementById("close-submit-backdrop")?.addEventListener("click", closeModal);
document.getElementById("submit-form")?.addEventListener("submit", submitForm);

loadApprovedSubmissions();
