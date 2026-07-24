# Course Generation Model — Training Setup

## 📋 Overview

This document describes the training environment setup for the **Course Generation Model** notebook.

## 🔧 Virtual Environment Setup

A dedicated Python virtual environment has been created for training the course generation model.

### Location
```
d:\HocThac\Ki2\IT2041.CH201\IT2041.CH201\venv\
```

### Installed Packages
- **pandas**: Data manipulation and analysis
- **openpyxl**: Excel file parsing (TKB_KHDT)
- **matplotlib**: Visualization
- **seaborn**: Statistical visualization
- **numpy**: Numerical computing
- **jupyter**: Jupyter notebook support
- **ipykernel**: IPython kernel for Jupyter

### Jupyter Kernel
- **Kernel Name**: `course-gen`
- **Display Name**: `Course Generation (venv)`
- **Location**: `C:\Users\tuan1\AppData\Roaming\jupyter\kernels\course-gen`

## 📓 Notebook Information

### File
```
notebooks/course_generation_model.ipynb
```

### Kernel Selection
When opening the notebook in VS Code or Jupyter:
1. Click the kernel selector (top-right corner)
2. Select **"Course Generation (venv)"** or **"course-gen"**
3. The notebook will use the virtual environment

### Notebook Structure (29 cells)

| Section | Description |
|---------|-------------|
| 1 | Load Ràng Buộc Môn từ Rules |
| 2 | Load Global Prerequisites |
| 3 | Load Course Catalog |
| 4 | Feature Engineering |
| 5 | Train Model |
| 6 | Predict Courses |
| 7 | Evaluate Model |
| 8 | Visualization |
| 9 | Parse Excel File (TKB_KHDT) |
| 10 | Interactive Input |
| 11 | Recommend Courses from Excel |
| 12 | Load Test Cases |
| 13 | Run Test Cases |

## 📊 Training Data

### Test Cases Location
```
data/train/
├── student_case_1_missing_english.json
├── student_case_2_retake_courses.json
├── student_case_3_missing_prerequisites.json
└── student_case_4_normal_progress.json
```

### Test Case Scenarios

#### Case 1: Missing English
- **Description**: Student completed basic courses but hasn't passed English requirement
- **Completed**: 18 courses
- **Expected**: Should recommend English courses (ENG01, ENG02, ENG03)

#### Case 2: Retake Courses
- **Description**: Student wants to retake courses to improve grades
- **Completed**: 21 courses
- **Retake**: IT002, MA003
- **Expected**: Should prioritize retake courses

#### Case 3: Missing Prerequisites
- **Description**: Student lacks prerequisites for advanced courses
- **Completed**: 17 courses (missing IT002-IT005)
- **Expected**: Should recommend foundation courses, NOT advanced courses

#### Case 4: Normal Progress
- **Description**: Student on track, ready for specialized courses
- **Completed**: 22 courses
- **Expected**: Should recommend specialized courses (SE005, SE100, SE101, SE102)

## 🚀 Running the Notebook

### Option 1: VS Code
1. Open `notebooks/course_generation_model.ipynb`
2. Select kernel: **"Course Generation (venv)"**
3. Run cells sequentially or use "Run All"

### Option 2: Jupyter Lab
```bash
cd d:\HocThac\Ki2\IT2041.CH201\IT2041.CH201
venv\Scripts\jupyter lab notebooks/course_generation_model.ipynb
```

### Option 3: Jupyter Notebook
```bash
cd d:\HocThac\Ki2\IT2041.CH201\IT2041.CH201
venv\Scripts\jupyter notebook notebooks/course_generation_model.ipynb
```

## 📈 Expected Output

When running the notebook, you should see:

1. **Load Constraints**: ✅ Loaded constraints for K2023/KTPM
2. **Load Prerequisites**: ✅ Loaded X courses with prerequisites
3. **Feature Engineering**: ✅ Extracted features for X courses
4. **Train Model**: ✅ Model trained for K2023/KTPM
5. **Predict**: ✅ Recommendations for student with X completed courses
6. **Evaluate**: ✅ Compliance, Coverage, Explainability metrics
7. **Parse Excel**: ✅ Parsed X courses from Excel file
8. **Test Cases**: ✅ Loaded 4 test cases
9. **Test Results**: ✅ Test summary with PASS/FAIL status

## 🔍 Troubleshooting

### Kernel Not Found
If the kernel doesn't appear in VS Code:
1. Reload VS Code window (Ctrl+Shift+P → "Developer: Reload Window")
2. Or reinstall kernel:
   ```bash
   venv\Scripts\python -m ipykernel install --user --name course-gen --display-name "Course Generation (venv)"
   ```

### Missing Packages
If you get import errors, reinstall packages:
```bash
venv\Scripts\pip install pandas openpyxl matplotlib seaborn numpy jupyter ipykernel
```

### Excel File Not Found
Ensure the file exists:
```
TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx
```

### Rules Files Not Found
Ensure the rules directory exists:
```
data/rules/local/K2023/KTPM.json
data/rules/global/course_prerequisites_catalog.json
```

## 📝 Notes

- The notebook uses **K2023/KTPM** (Khóa 2023, Kỹ Thuật Phần Mềm) as the default cohort/major
- Test cases are loaded from `data/train/` directory
- Excel parsing uses fuzzy column matching to handle Vietnamese diacritics
- The model uses a constraint-based approach (prerequisites, course groups)
- Recommendations are ranked by impact (unlocks other courses), required status, and credits

## 🎯 Next Steps

1. Run the notebook with the virtual environment
2. Verify all test cases pass
3. Extend test cases for other cohorts/majors
4. Integrate model into the main application
5. Add more evaluation metrics (e.g., student satisfaction, graduation time)
