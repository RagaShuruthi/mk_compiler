const editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");
editor.session.setMode("ace/mode/python");
const runBtn = document.getElementById("runBtn");
const inputFieldsContainer = document.getElementById("inputFields");
const output = document.getElementById("output");
const timeContent = document.getElementById("complexity");
const traceContent = document.getElementById("trace");
const saveBtn = document.getElementById("saveBtn");
const loadBtn = document.getElementById("loadBtn");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const startBtn = document.getElementById("startBtn");
const lastBtn = document.getElementById("lastBtn");
const complexityGraphCanvas = document.getElementById("complexityGraph");
let chartInstance = null;
let traceSteps = [];
let currentTraceIndex = 0;
async function executeCode(code, inputs) {
  runBtn.disabled = true;
  runBtn.textContent = "Running...";
  output.textContent = "Running code...";
  traceContent.textContent = "Analyzing...";
  timeContent.textContent = "Calculating...";
  try {
    const response = await fetch("/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, inputs }),
    });
    const data = await response.json();
    if (data.error) {
      output.textContent = `Error:\n${data.error}`;
    } else {
      output.textContent = data.output;
    }
    traceSteps = data.trace || [];
    currentTraceIndex = 0;
    traceContent.innerHTML = "";
    if (traceSteps.length > 0) {
      showTraceStep(currentTraceIndex);
    }
    updateTraceButtons(traceSteps);
    visualizeTimeComplexity(data.time_complexity, data.execution_time);
  } catch (err) {
    output.textContent = "Server error. Check console.";
    console.error(err);
  }
  runBtn.disabled = false;
  runBtn.textContent = "Run";
}
function visualizeTimeComplexity(timeComplexity, executionTime) {
  const ctx = complexityGraphCanvas.getContext("2d");
  let dataPoints = [1, 2, 3, 4, 5];
  let timeValues;
  switch (timeComplexity) {
    case "O(1)":
      timeValues = dataPoints.map(() => executionTime);
      break;
    case "O(n)":
      timeValues = dataPoints.map(n => executionTime * n);
      break;
    case "O(n^2)":
      timeValues = dataPoints.map(n => executionTime * n * n);
      break;
    case "O(log n)":
      timeValues = dataPoints.map(n => executionTime * Math.log2(n));
      break;
    default:
      timeValues = dataPoints.map(() => executionTime);
  }
  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: dataPoints,
      datasets: [{
        label: `Time Complexity (${timeComplexity})`,
        data: timeValues,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        fill: false,
        tension: 0.2
      }]
    },
    options: {
      responsive: true,
      scales: {
        x: { title: { display: true, text: 'Input Size' } },
        y: { title: { display: true, text: 'Execution Time (s)' }, beginAtZero: true }
      }
    }
  });

  timeContent.innerHTML = `Estimated Complexity: ${timeComplexity}<br/>Execution Time: ${executionTime} sec`;
}

runBtn.onclick = () => {
  const code = editor.getValue();
  const inputMatches = code.match(/input\([^\)]*\)/g) || [];

  inputFieldsContainer.innerHTML = "";

  if (inputMatches.length > 0) {
    runBtn.textContent = "Fill Inputs";
    runBtn.disabled = true;

    const inputs = new Array(inputMatches.length);
    inputMatches.forEach((_, index) => {
      const inputElement = document.createElement("input");
      inputElement.type = "text";
      inputElement.placeholder = `Input ${index + 1}`;
      inputElement.className = "userInput";
      inputFieldsContainer.appendChild(inputElement);

      inputElement.addEventListener("input", () => {
        inputs[index] = inputElement.value;
        const allFilled = inputs.every((val) => val?.trim() !== "");
        if (allFilled) {
          runBtn.disabled = false;
          runBtn.textContent = "Run";
          runBtn.onclick = () => executeCode(code, inputs);
        }
      });
    });

    inputFieldsContainer.style.display = "block";
  } else {
    executeCode(code, []);
  }
};

function showTraceStep(index) {
  traceContent.innerHTML = "";
  const traceBox = document.createElement("div");
  traceBox.className = "traceBox";
  traceBox.textContent = traceSteps[index].content;
  traceContent.appendChild(traceBox);

  const stepCounter = document.createElement("div");
  stepCounter.style.marginTop = "10px";
  stepCounter.style.fontSize = "14px";
  stepCounter.style.color = "#ccc";
  stepCounter.textContent = `Step ${index + 1} / ${traceSteps.length}`;
  traceContent.appendChild(stepCounter);
}

function updateTraceButtons(steps) {
  prevBtn.disabled = false;
  startBtn.disabled = false;
  nextBtn.disabled = false;
  lastBtn.disabled = false;
}

startBtn.onclick = () => { currentTraceIndex = 0; showTraceStep(currentTraceIndex); updateTraceButtons(traceSteps); };
prevBtn.onclick = () => { if (currentTraceIndex > 0) currentTraceIndex--; showTraceStep(currentTraceIndex); updateTraceButtons(traceSteps); };
nextBtn.onclick = () => { if (currentTraceIndex < traceSteps.length - 1) currentTraceIndex++; showTraceStep(currentTraceIndex); updateTraceButtons(traceSteps); };
lastBtn.onclick = () => { currentTraceIndex = traceSteps.length - 1; showTraceStep(currentTraceIndex); updateTraceButtons(traceSteps); };

document.addEventListener("keydown", (e) => {
  if (!traceSteps.length) return;

  switch (e.key) {
    case "ArrowRight": nextBtn.click(); break;
    case "ArrowLeft": prevBtn.click(); break;
    case "Home": startBtn.click(); break;
    case "End": lastBtn.click(); break;
  }
});


saveBtn.onclick = () => {
  const code = editor.getValue();
  const blob = new Blob([code], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "code.py";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

loadBtn.onclick = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".py,.txt";

  input.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      editor.setValue(e.target.result, 1);
      alert("Code loaded!");
    };
    reader.readAsText(file);
  };

  input.click();
};

const resizer = document.querySelector(".resizer");
const leftContainer = document.querySelector("#left-container");
const rightContainer = document.querySelector("#right-container");

let isResizing = false;

resizer.addEventListener("mousedown", (e) => {
  isResizing = true;
  document.body.style.cursor = "col-resize";

  const resize = (e) => {
    if (!isResizing) return;
    const leftWidth = e.clientX;
    leftContainer.style.width = `${leftWidth}px`;
    rightContainer.style.width = `${window.innerWidth - leftWidth}px`;
  };

  document.addEventListener("mousemove", resize);
  document.addEventListener("mouseup", () => {
    isResizing = false;
    document.body.style.cursor = "default";
    document.removeEventListener("mousemove", resize);
  }, { once: true });
});
