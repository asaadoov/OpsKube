const API_BASE = "http://localhost:8080/api";

const tokenKey = "jwtToken";

function getToken() {
  return localStorage.getItem(tokenKey);
}

function setToken(token) {
  localStorage.setItem(tokenKey, token);
}

function clearToken() {
  localStorage.removeItem(tokenKey);
}

// DOM Elements
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const todoForm = document.getElementById("todo-form");
const todoInput = document.getElementById("todo-input");
const todoList = document.getElementById("todo-list");
const userEmailSpan = document.getElementById("user-email");
const logoutBtn = document.getElementById("logout-btn");

document.getElementById("switch-to-register").onclick = (e) => {
  e.preventDefault();
  loginForm.style.display = "none";
  registerForm.style.display = "block";
};

document.getElementById("switch-to-login").onclick = (e) => {
  e.preventDefault();
  registerForm.style.display = "none";
  loginForm.style.display = "block";
};

logoutBtn.onclick = () => {
  clearToken();
  renderUI();
};

// Submit Login
loginForm.onsubmit = async (e) => {
  e.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;

  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (res.ok) {
    const data = await res.json();
    setToken(data.access_token);
    renderUI();
  } else {
    alert("Login failed");
  }
};

// Submit Register
registerForm.onsubmit = async (e) => {
  e.preventDefault();
  const first_name = document.getElementById("register-first-name").value;
  const last_name = document.getElementById("register-last-name").value;
  const email = document.getElementById("register-email").value;
  const password = document.getElementById("register-password").value;

  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ first_name, last_name, email, password }),
  });

  if (res.ok) {
    alert("Registered successfully. You can now log in.");
    document.getElementById("switch-to-login").click();
  } else {
    alert("Registration failed");
  }
};

// Submit Todo
todoForm.onsubmit = async (e) => {
  e.preventDefault();
  const title = todoInput.value;
  const token = getToken();

  const res = await fetch(`${API_BASE}/todos`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title }),
  });

  if (res.ok) {
    todoInput.value = "";
    loadTodos();
  } else {
    alert("Failed to add todo");
  }
};

async function loadUser() {
  const token = getToken();
  if (!token) return null;

  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!res.ok) throw new Error("Token invalid");
    return await res.json();
  } catch (err) {
    clearToken();
    return null;
  }
}

async function loadTodos() {
  const token = getToken();
  const res = await fetch(`${API_BASE}/todos`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) return;

  const todos = await res.json();
  todoList.innerHTML = "";

  for (const todo of todos) {
    const li = document.createElement("li");
    li.classList.add("todo", "standard-todo");
    if (todo.completed) li.classList.add("completed");

    li.innerHTML = `
      <li class="todo-item">${todo.title}</li>
      <button class="check-btn"><i>✔️</i></button>
      <button class="delete-btn"><i>🗑️</i></button>
    `;

    li.querySelector(".check-btn").onclick = async () => {
      await fetch(`${API_BASE}/todos/${todo.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ completed: !todo.completed }),
      });
      loadTodos();
    };

    li.querySelector(".delete-btn").onclick = async () => {
      await fetch(`${API_BASE}/todos/${todo.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      loadTodos();
    };

    todoList.appendChild(li);
  }
}

async function renderUI() {
  const user = await loadUser();

  const authForms = document.getElementById("auth-forms");
  const todoForm = document.getElementById("todo-form");
  const userInfo = document.getElementById("user-info");

  if (user) {
    userEmailSpan.textContent = user.email;
    authForms.style.display = "none";
    userInfo.style.display = "block";
    todoForm.style.display = "flex";
    loadTodos();
  } else {
    authForms.style.display = "block";
    userInfo.style.display = "none";
    todoForm.style.display = "none";
    todoList.innerHTML = "";
  }
}

// Theme switching
function changeTheme(theme) {
  document.body.className = theme;

  const input = document.querySelector("#todo-input");
  const button = document.querySelector(".todo-btn");
  const todos = document.querySelectorAll(".todo");

  if (input) {
    input.className = `${theme}-input`;
  }

  if (button) {
    button.className = `${theme}-button`;
  }

  todos.forEach((todo) => {
    todo.className = `todo ${theme}-todo`;
  });

  const title = document.getElementById("title");
  if (theme === "darker") {
    title.classList.add("darker-title");
  } else {
    title.classList.remove("darker-title");
  }
}

window.onload = () => {
  renderUI();
  changeTheme("standard");
};
