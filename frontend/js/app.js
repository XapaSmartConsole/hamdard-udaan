// =====================================================
// RSPL DEMO – COMMON JS LOGIC (PORT 8001)
// =====================================================

console.log('🔌 Current hostname:', window.location.hostname);
console.log('🔌 Is localhost?', window.location.hostname === 'localhost');

const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? "http://127.0.0.1:8001/api"  // Local development
    : "https://hamdard-udaan-1.onrender.com/api";  // Production on Vercel

console.log('🔌 API_BASE:', API_BASE);
const isKycPage = window.location.pathname.includes("kyc.html");
let AVAILABLE_POINTS = 0;
let REDEEMED_POINTS = 0;   

// =====================================================
// UTILITIES
// =====================================================
function getUserId() {
  return localStorage.getItem("user_id");
}

function showMessage(msg) {
  alert(msg);
}

// =====================================================
// WALLET SUMMARY (🔥 IMPORTANT)
// =====================================================
async function loadWalletSummary() {
  const userId = getUserId();
  if (!userId) return;

  try {
    const res = await fetch(`${API_BASE}/wallet/summary?user_id=${userId}`);
    const data = await res.json();

    AVAILABLE_POINTS = data.points ?? 0;
    REDEEMED_POINTS  = data.redeemed ?? 0;

    // Home / Dashboard circles
    if (document.getElementById("total-points")) {
      document.getElementById("total-points").innerText = AVAILABLE_POINTS;
    }

    if (document.getElementById("redeemed-points")) {
      document.getElementById("redeemed-points").innerText = REDEEMED_POINTS;
    }

    // Wallet page (if exists)
    if (document.getElementById("available-points")) {
      document.getElementById("available-points").innerText = AVAILABLE_POINTS;
    }

    if (document.getElementById("total-redeemed")) {
      document.getElementById("total-redeemed").innerText = REDEEMED_POINTS;
    }

  } catch (err) {
    console.warn("⚠️ Wallet summary not loaded", err);
  }
}

// =====================================================
// DOM READY
// =====================================================
    document.addEventListener("DOMContentLoaded", () => {
        loadWalletSummary();
        loadKycStatus();

    // =====================================================
    // SIGNUP
    // =====================================================
    const signupForm = document.getElementById("signup-form");
    if (signupForm) {
        signupForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const full_name = document.getElementById("full_name").value.trim();
        const phone = document.getElementById("phone").value.trim();

        if (!full_name || !phone) {
            return showMessage("Please enter full name and mobile number");
        }

        try {
            const res = await fetch(
            `${API_BASE}/signup?full_name=${encodeURIComponent(full_name)}&phone=${phone}`,
            { method: "POST" }
            );
            const data = await res.json();

            if (data.status === "exists") {
            showMessage("User already registered. Please login.");
            } else {
            showMessage("Account created successfully.");
            }

            window.location.href = "index.html";
        } catch {
            showMessage("Signup failed");
        }
        });
    }

    // =====================================================
    // SEND OTP
    // =====================================================
    // ================= SEND OTP =================
    const sendOtpBtn = document.getElementById("send-otp-btn");
    if (sendOtpBtn) {
    sendOtpBtn.addEventListener("click", async () => {
        const phone = document.getElementById("phone").value.trim();
        if (!phone) return alert("Enter mobile number");

        await fetch(`${API_BASE}/send-otp?phone=${phone}`, { method: "POST" });

        alert("OTP sent successfully");

        // 🔥 SHOW OTP FIELD + CONTINUE BUTTON
        document.getElementById("otp").style.display = "block";
        document.getElementById("verify-otp-btn").style.display = "block";

        // OPTIONAL: hide send button
        sendOtpBtn.style.display = "none";
    });
    }


    // =====================================================
    // VERIFY OTP
    // =====================================================
    const verifyOtpBtn = document.getElementById("verify-otp-btn");
    if (verifyOtpBtn) {
    verifyOtpBtn.addEventListener("click", async () => {
        const phone = document.getElementById("phone").value.trim();
        const otp = document.getElementById("otp").value.trim();

        if (!phone || !otp) return alert("Enter OTP");

        const res = await fetch(
        `${API_BASE}/verify-otp?phone=${phone}&otp=${otp}`,
        { method: "POST" }
        );
        const data = await res.json();

        if (!data.success) return alert("Invalid OTP");

        localStorage.setItem("user_id", data.user_id);
        window.location.href = "home.html";
    });
    }


    // =====================================================
    // DASHBOARD KYC SUMMARY
    // =====================================================
    if (document.getElementById("kyc-total")) {
        fetch(`${API_BASE}/kyc/summary`)
        .then(res => res.json())
        .then(data => {
            document.getElementById("kyc-total").innerText = data.total;
            document.getElementById("kyc-completed").innerText = data.completed;
            document.getElementById("kyc-pending").innerText = data.pending;
        });
    }

    // =====================================================
    // KYC SUBMISSION
    // =====================================================
    const kycForm = document.getElementById("kyc-form");
    if (kycForm) {
        kycForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const aadhaar = document.getElementById("aadhaar").value.trim();
        const pan = document.getElementById("pan").value.trim();

        if (!aadhaar || !pan) return showMessage("Enter Aadhaar and PAN");

        await fetch(
            `${API_BASE}/kyc?user_id=${getUserId()}&aadhaar=${aadhaar}&pan=${pan}`,
            { method: "POST" }
        );

        showMessage("✅ KYC Completed Successfully");
        window.location.reload();
        });
    }

    // =====================================================
    // BANK DETAILS (KYC PROTECTED)
    // =====================================================
    const bankForm = document.getElementById("bank-form");
    if (bankForm) {
        bankForm.addEventListener("submit", async (e) => {
        e.preventDefault();

        const userId = getUserId();
        if (!userId) return showMessage("User not logged in");

        const kycRes = await fetch(`${API_BASE}/kyc/status?user_id=${userId}`);
        const kycData = await kycRes.json();

        if (kycData.kyc_status !== "COMPLETED") {
            return showMessage("❌ Please complete KYC before bank transfer");
        }

        const holder = document.getElementById("holder").value.trim();
        const bank = document.getElementById("bank").value.trim();
        const acc = document.getElementById("acc").value.trim();
        const ifsc = document.getElementById("ifsc").value.trim();

        if (!holder || !bank || !acc || !ifsc) {
            return showMessage("Please enter all bank details");
        }

        await fetch(
            `${API_BASE}/bank?user_id=${userId}&account_holder_name=${encodeURIComponent(holder)}&bank_name=${encodeURIComponent(bank)}&account_number=${acc}&ifsc=${ifsc}`,
            { method: "POST" }
        );

        showMessage("✅ Bank details saved successfully");
        });
    }

    // =====================================================
    // ADD AMOUNT
    // =====================================================
    const addAmountBtn = document.getElementById("add-amount-btn");
    if (addAmountBtn) {
        addAmountBtn.addEventListener("click", async () => {
        const amount = document.getElementById("amount").value.trim();
        if (!amount || isNaN(amount)) return showMessage("Enter valid amount");

        const res = await fetch(
            `${API_BASE}/wallet?user_id=${getUserId()}&amount=${amount}`,
            { method: "POST" }
        );
        const data = await res.json();

        showMessage(`₹${amount} added → ${data.points} points credited`);
        loadWalletSummary();
        document.addEventListener("DOMContentLoaded", () => {
        loadWalletSummary();
          // 🔥 THIS WAS MISSING
    });

        });
    }

  // =====================================================
  // REDEEM POINTS
  // =====================================================
  const redeemBtn = document.getElementById("redeem-btn");
  if (redeemBtn) {
    redeemBtn.addEventListener("click", async () => {
      const points = document.getElementById("points").value.trim();
      if (!points || isNaN(points)) return showMessage("Enter valid points");

      await fetch(
        `${API_BASE}/redeem?user_id=${getUserId()}&points=${points}`,
        { method: "POST" }
      );

      showMessage("Points redeemed successfully");
      loadWalletSummary();
    });
  }

  // 🔥 Load wallet automatically
  loadWalletSummary();
});

// =====================================================
// LOAD KYC USERS (ADMIN VIEW)
// =====================================================
if (isKycPage) {
  fetch(`${API_BASE}/kyc/users`)
    .then(res => res.json())
    .then(users => {
      const list = document.getElementById("kyc-user-list");
      if (!list) return;

      let completed = 0, pending = 0;
      list.innerHTML = "";

      users.forEach(u => {
        const done = u.kyc_status === "COMPLETED";
        done ? completed++ : pending++;

        list.innerHTML += `
          <div class="kyc-user ${done ? "completed" : "pending"}">
            <div>
              <strong>Name:</strong> ${u.full_name}<br>
              <strong>Mobile:</strong> ${u.phone}<br>
              <strong>Status:</strong> KYC ${done ? "Completed" : "Pending"}
            </div>
            <button class="btn-secondary" ${done ? "disabled" : ""}>
              ${done ? "Completed" : "Complete KYC"}
            </button>
          </div>
        `;
      });

      document.getElementById("total-users").innerText = users.length;
      document.getElementById("kyc-completed").innerText = completed;
      document.getElementById("kyc-pending").innerText = pending;
    });
}
// =====================================================
// LOAD KYC STATUS (FOR HOME DASHBOARD)
// =====================================================
function loadKycStatus() {
  fetch(`${API_BASE}/kyc/summary`)
    .then(res => res.json())
    .then(data => {
      if (document.getElementById("kyc-completed")) {
        document.getElementById("kyc-completed").innerText = data.completed ?? 0;
      }
      if (document.getElementById("kyc-pending")) {
        document.getElementById("kyc-pending").innerText = data.pending ?? 0;
      }
    })
    .catch(() => console.warn("KYC status not loaded"));
}

// =====================================================
// REWARDS CATALOG + CART LOGIC
// =====================================================

// ================= CART HELPERS (USER-SPECIFIC) =================
function getCartKey() {
  const userId = localStorage.getItem("user_id");
  return `reward_cart_user_${userId}`;
}

function getCart() {
  return JSON.parse(localStorage.getItem(getCartKey())) || [];
}

function saveCart(cart) {
  localStorage.setItem(getCartKey(), JSON.stringify(cart));
}



// =====================================================
// ADD TO CART (POINTS CHECK)
// =====================================================
function addToCart(productName, requiredPoints) {

  if (REDEEMED_POINTS < requiredPoints) {
    return alert("❌ Not enough redeemed points");
  }

  let cart = getCart();

  if (cart.find(item => item.name === productName)) {
    return alert("⚠️ Product already in cart");
  }

  cart.push({
    name: productName,
    points: requiredPoints
  });

  saveCart(cart);

  alert(`✅ ${productName} added to cart`);
}



// =====================================================
// VIEW PRODUCT
// =====================================================
function viewProduct(productName, requiredPoints) {
  alert(
    `🎁 ${productName}\n\nPoints Required: ${requiredPoints}\n\nRedeemed Points Available: ${REDEEMED_POINTS}
`
  );
}


// =====================================================
// FINAL REDEEM (CHECKOUT)
// =====================================================
async function checkoutRewards() {
  const userId = getUserId();
  if (!userId) return showMessage("Please login");

  const cart = getCart();
  if (cart.length === 0) return showMessage("Cart is empty");

  const totalPoints = cart.reduce((sum, i) => sum + i.points, 0);

  if (AVAILABLE_POINTS < 0) {
    return showMessage("❌ Invalid cart state");
  }

  const res = await fetch(
    `${API_BASE}/redeem?user_id=${userId}&points=${totalPoints}`,
    { method: "POST" }
  );

  if (!res.ok) return showMessage("Redemption failed");

  localStorage.removeItem("reward_cart");
  showMessage("🎉 Rewards redeemed successfully");

  loadWalletSummary(); // refresh from backend
}
