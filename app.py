from flask import Flask, request, jsonify
import pyodbc
import pandas as pd
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io,warnings
import base64

import numpy as np


app = Flask(__name__)

# Set up the connection to the SQL Server
def get_db_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};'
        'SERVER=SQL5111.site4now.net;'  # server name
        'DATABASE=db_a9e9e8_schoolerpdev;'  # database name
        'UID=db_a9e9e8_schoolerpdev_admin;'  # username
        'PWD=DevEnv@123;'  # password
    )
    return conn

# Query to load student data with Subject Name from Exam Marks
def load_student_data_from_db(conn, student_id, class_id, session_id, section_id, exam_id=None):
    query = f"""
        SELECT 
            em.StudentId,
            em.MarksObtain,
            em.ExamId,
            s.Name AS SubjectName,
            em.SubjectId,
            em.ClassId,
            em.SessionId,
            em.SectionId
        FROM 
            ExamMarks em
        JOIN 
            Subject s ON em.SubjectId = s.ID
        WHERE
            em.StudentId = {student_id}
            AND em.ClassId = {class_id}
            AND em.SessionId = {session_id}
            AND em.SectionId = {section_id}
    """
    
    # Only filter by exam_id if it's provided (not 'all')
    if exam_id and exam_id != 'all':
        query += f" AND em.ExamId = {exam_id}"

    df = pd.read_sql(query, conn)
    return df

# Function to load the ExamId to ExamName mapping
def load_exam_mapping(conn):
    query = "SELECT id, Name FROM Exam"
    df = pd.read_sql(query, conn)
    exam_mapping = dict(zip(df['id'], df['Name']))
    return exam_mapping

# Function to extract student data
def extract_student_data(df):
    subjects = df['SubjectId'].unique().tolist()
    return df, subjects

# Custom anomaly detection comparing each exam to previous exams
def detect_anomalies_compare_all(marks, threshold=5):
    anomalies = {'down': [], 'up': []}
    for i in range(1, len(marks)):
        if marks[i] is not None and marks[i-1] is not None:  # Check if both values are not None
            if abs(marks[i] - marks[i-1]) > threshold:
                if marks[i] < marks[i-1]:
                    anomalies['down'].append(i)
                elif marks[i] > marks[i-1]:
                    anomalies['up'].append(i)
    return anomalies

# Function to detect attendance anomalies
def detect_attendance_anomalies(attendance, threshold=5):
    anomalies = {'down': [], 'up': []}
    for i in range(1, len(attendance)):
        if attendance[i] is not None and attendance[i-1] is not None:
            if abs(attendance[i] - attendance[i-1]) > threshold:
                if attendance[i] < attendance[i-1]:
                    anomalies['down'].append(i)
                elif attendance[i] > attendance[i-1]:
                    anomalies['up'].append(i)
    return anomalies

# Function to calculate average percentage per exam
def calculate_average_percentage(df):
    exam_groups = df.groupby(['ClassId', 'SessionId', 'ExamId'])
    averages = exam_groups['MarksObtain'].mean().reset_index(name='AveragePercentage')
    averages['ExamLabel'] = averages['ExamId'].apply(lambda x: f"Exam {x}")
    return averages

# Fetch exam schedule data
def get_exam_start_months(conn, class_id):
    query = f"""
        SELECT 
            ExamId,
            Format(ExamStartDate, 'yyyy/MM/dd') as ExamDate
        FROM 
            ExamSchedule
        WHERE
            ClassId = {class_id}
    """
    df = pd.read_sql(query, conn)
    df['ExamStartMonth'] = df['ExamDate'].apply(lambda x: datetime.strptime(x, "%Y/%m/%d").month)
    return df[['ExamId', 'ExamStartMonth']]

# Load attendance data
def load_attendance_data_from_db(conn, student_id, class_id):
    query = f"""
        SELECT 
            Month,
            NoofDaysPresent,
            NoofEligibleDays
        FROM 
            MonthlyAttendance
        WHERE
            StudentId = {student_id}
            AND ClassId = {class_id}
    """
    df = pd.read_sql(query, conn)
    df['AttendancePercentage'] = (df['NoofDaysPresent'] / df['NoofEligibleDays']) * 100
    return df

# Determine attendance period based on exam_id
def determine_attendance_period(exam_id, exam_start_months):
    exam_periods = {}
    
    # Safe lookup function
    def get_exam_period(exam_id, exam_start_months):
        exam_months = exam_start_months[exam_start_months['ExamId'] == exam_id]
        if not exam_months.empty:
            return exam_months['ExamStartMonth'].values[0]
        return None
    
    # Get the start and end months for the exams
    first_exam_start = get_exam_period(1, exam_start_months)
    second_exam_start = get_exam_period(2, exam_start_months)
    third_exam_start = get_exam_period(3, exam_start_months)
    
    if first_exam_start:
        exam_periods[1] = (4, first_exam_start - 1)
    if first_exam_start and second_exam_start:
        exam_periods[2] = (first_exam_start, second_exam_start - 1)
    if second_exam_start and third_exam_start:
        exam_periods[3] = (second_exam_start, third_exam_start - 1)
    
    # If the user requests 'all', return all periods, otherwise return the specific period
    if exam_id == 'all':
        return exam_periods
    else:
        return {int(exam_id): exam_periods.get(int(exam_id), None)}

# Plot attendance data with attendance for specific subject ids
# Plot marks and attendance with attendance anomalies
def plot_marks_attendance_specific(df, student_id, subject_id, averages, plot_attendance=True):
     # Map exam IDs to their labels
    exam_label_map = {1: 'First Term', 2: 'Half Yearly', 3: 'Final Term'}
    exam_ids = sorted(averages.keys())
    avg_attendance_values = [averages[exam_id] for exam_id in exam_ids]
    
    # Filter the student data for the specific subject
    student_data = df[df['SubjectId'] == subject_id]
    
    if student_data.empty:
        marks = [0] * len(exam_ids)
        subject_name = f"Subject {subject_id}"
    else:
        student_data = student_data[student_data['ExamId'].isin(exam_ids)].sort_values(by=['ClassId', 'SessionId', 'ExamId'])
        subject_name = student_data['SubjectName'].iloc[0] if 'SubjectName' in student_data.columns else f"Subject {subject_id}"
        marks = student_data['MarksObtain'].tolist()
    
        # Handle missing marks for some exams
        marks = [student_data[student_data['ExamId'] == x]['MarksObtain'].mean() if x in student_data['ExamId'].values else 0 for x in exam_ids]

    # Detect anomalies for both marks and attendance
    marks_anomalies = detect_anomalies_compare_all(marks)
    attendance_anomalies = detect_attendance_anomalies(avg_attendance_values)

    plt.figure(figsize=(16, 8))
    
    # Plot attendance only if required
    if plot_attendance:
        plt.plot(exam_ids, avg_attendance_values, marker='o', linestyle='-', color='orange', label='Average Attendance')
    
        # Highlight anomalies in attendance
        for i in range(len(avg_attendance_values)):
            if i in attendance_anomalies['down']:
                plt.scatter(exam_ids[i], avg_attendance_values[i], color='red', s=150, label='Attendance Decrease' if i == 0 else "")
            elif i in attendance_anomalies['up']:
                plt.scatter(exam_ids[i], avg_attendance_values[i], color='green', s=150, label='Attendance Increase' if i == 0 else "")
    
    # Plot marks
    plt.plot(exam_ids, marks, marker='o', linestyle='-', color='blue', label=f'Subject: {subject_name}')
    
    # Highlight anomalies in marks
    for i in range(len(marks)):
        if i in marks_anomalies['down']:
            plt.scatter(exam_ids[i], marks[i], color='red', s=150, label='Marks Decrease' if i == 0 else "")
        elif i in marks_anomalies['up']:
            plt.scatter(exam_ids[i], marks[i], color='green', s=150, label='Marks Increase' if i == 0 else "")
    
    plt.title(f'Marks and {"Attendance" if plot_attendance else ""} for Subject {subject_name} Anomalies for Student {student_id}')
    plt.xlabel('Exam')
    plt.ylabel('Percentage (%)')
    plt.ylim(0, 108)
    plt.yticks(np.arange(0, 101, 10))
    exam_labels = [exam_label_map.get(exam_id, f"Exam {exam_id}") for exam_id in exam_ids]
    plt.xticks(exam_ids, labels=exam_labels) 
    plt.grid(True)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))

    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return img_base64

warnings.filterwarnings("ignore")

# Function to plot marks and attendance for all subjects 
def plot_marks_attendance_allsubject(df, student_id, averages, plot_attendance=True):
    # Map exam IDs to their labels
    exam_label_map = {1: 'First Term', 2: 'Half Yearly', 3: 'Final Term'}
    # Prepare the exam IDs for plotting
    exam_ids = sorted(averages.keys())

    # Create the figure
    plt.figure(figsize=(16, 8))

    # Debugging: print exam_ids
    print(f'Exam ID: {exam_ids}')

    # Plot average attendance if required
    if plot_attendance:
        attendance_values = [averages[exam_id] for exam_id in exam_ids]
        plt.plot(exam_ids, attendance_values, marker='o', linestyle='-', color='orange', label='Average Attendance')

        # Detect anomalies for attendance
        anomalies_attendance = detect_anomalies_compare_all(attendance_values)

        # Highlight attendance anomalies with different colors
        for j in range(len(attendance_values)):
            if j in anomalies_attendance['down']:
                plt.scatter(exam_ids[j], attendance_values[j], color='red', s=150, label='Anomaly - Attendance Decrease' if j == 0 else "")
            elif j in anomalies_attendance['up']:
                plt.scatter(exam_ids[j], attendance_values[j], color='green', s=150, label='Anomaly - Attendance Increase' if j == 0 else "")

    # Plot marks for each subject
    subjects = df['SubjectId'].unique()

    for subject_id in subjects:
        subject_data = df[df['SubjectId'] == subject_id]
        subject_name = subject_data['SubjectName'].iloc[0]

        # Group by ExamId and get the mean of MarksObtain
        marks_series = subject_data.groupby('ExamId')['MarksObtain'].mean()

        # Create a new Series with all exam_ids and fill missing values with 0
        marks = marks_series.reindex(exam_ids, fill_value=0).tolist()

        # Debugging: print marks for the subject
        print(f'Marks for {subject_name}: {marks}')

        # Detect anomalies
        anomalies = detect_anomalies_compare_all(marks)

        # Plot the marks for the subject
        plt.plot(exam_ids, marks, marker='o', linestyle='-', label=f'Subject: {subject_name}')

        # Highlight anomalies with different colors
        for j in range(len(marks)):
            if j in anomalies['down']:
                plt.scatter(exam_ids[j], marks[j], color='red', s=150, label='Anomaly - Marks Decrease' if j == 0 else "")
            elif j in anomalies['up']:
                plt.scatter(exam_ids[j], marks[j], color='green', s=150, label='Anomaly - Marks Increase' if j == 0 else "")

    # Set titles and labels
    plt.title(f'Marks {"and Attendance" if plot_attendance else ""} for All Subjects for Student {student_id}')
    plt.xlabel('Exam ID')
    plt.ylabel('Percentage (%)')
    plt.yticks(np.arange(0, 101, 10))
    plt.xlim(min(exam_ids) - 0.1, max(exam_ids) + 0.1)
    exam_labels = [exam_label_map.get(exam_id, f"Exam {exam_id}") for exam_id in exam_ids]
    plt.xticks(exam_ids, labels=exam_labels) 
    plt.ylim(0, 108)
    plt.grid(True)
    
    # Move the legend outside the plot
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))

    # Adjust layout to remove extra spaces
    plt.tight_layout()

    # Save and return the plot as base64
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return img_base64




# Function to plot cumulative percentage for all subjects
def plot_marks_attendance_cumulative_percentage(df, student_id, averages, plot_attendance=True):

     # Map exam IDs to their labels
    exam_label_map = {1: 'First Term', 2: 'Half Yearly', 3: 'Final Term'}
    # Prepare the exam IDs and average values for attendance plotting
    exam_ids = sorted(averages.keys())
    avg_attendance_values = [averages[exam_id] for exam_id in exam_ids]

    # Calculate the average marks across all subjects for each exam
    avg_marks_per_exam = df.groupby('ExamId')['MarksObtain'].mean().reindex(exam_ids)

    # Handle missing exams where the student doesn't have marks
    avg_marks_per_exam.fillna(0, inplace=True)

    # Detect anomalies in the average marks and attendance
    anomalies_marks = detect_anomalies_compare_all(avg_marks_per_exam.tolist())
    anomalies_attendance = detect_anomalies_compare_all(avg_attendance_values) if plot_attendance else None

    # Create a figure and a single subplot
    plt.figure(figsize=(16, 8))

    # Plot attendance only if the user chose to plot it
    if plot_attendance:
        plt.plot(exam_ids, avg_attendance_values, marker='o', linestyle='-', color='orange', label='Average Attendance')

        # Highlight attendance anomalies
        for i in range(len(avg_attendance_values)):
            if i in anomalies_attendance['down']:
                plt.scatter(exam_ids[i], avg_attendance_values[i], color='red', s=150, label='Anomaly - Attendance Decrease' if i == 0 else "")
            elif i in anomalies_attendance['up']:
                plt.scatter(exam_ids[i], avg_attendance_values[i], color='green', s=150, label='Anomaly - Attendance Increase' if i == 0 else "")

    # Plot average marks on the same axes
    plt.plot(exam_ids, avg_marks_per_exam, marker='o', linestyle='-', color='blue', label='Average Marks')

    # Highlight marks anomalies
    for i in range(len(avg_marks_per_exam)):
        if i in anomalies_marks['down']:
            plt.scatter(exam_ids[i], avg_marks_per_exam.iloc[i], color='red', s=150, label='Anomaly - Marks Decrease' if i == 0 else "")
        elif i in anomalies_marks['up']:
            plt.scatter(exam_ids[i], avg_marks_per_exam.iloc[i], color='green', s=150, label='Anomaly - Marks Increase' if i == 0 else "")

    # Titles and labels
    plt.title(f'{"Attendance and " if plot_attendance else ""}Average Percentage Across All Subjects for Student {student_id}')
    plt.xlabel('Exam')
    plt.ylabel('Percentage (%)')
    plt.ylim(0, 108)
    plt.yticks(np.arange(0, 101, 10))
     # Use exam labels instead of IDs for the x-axis ticks
    exam_labels = [exam_label_map.get(exam_id, f"Exam {exam_id}") for exam_id in exam_ids]
    plt.xticks(exam_ids, labels=exam_labels)  # Label with exam IDs

    # Legends and grid
    plt.grid(True)
    # Move the legend outside the plot
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))

    # Save and return the plot as base64
    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return img_base64


# Flask route to analyze attendance data with filtering by exam ID
@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    student_id = data.get('student_id')
    class_id = data.get('class_id')
    selected_exam_id = data.get('exam_id')  # Default to 'all' if no exam_id is provided
    session_id = data.get('session_id')
    section_id = data.get('section_id')
    subject_choice = data.get('subject_choice')  # either 'specific' or 'all'
    plot_attendance = data.get('plot_attendance', 'yes')  # Added option for plotting attendance
    conn = get_db_connection()

    # Fetch exam start months
    exam_start_months = get_exam_start_months(conn, class_id)

    # Fetch attendance data
    attendance_data = load_attendance_data_from_db(conn, student_id, class_id)

    # Only determine attendance periods if attendance plotting is required
    if plot_attendance.lower() == 'yes':
        # Determine the attendance periods based on the selected exam term
        exam_periods = determine_attendance_period(selected_exam_id, exam_start_months)

        # Calculate attendance averages for the selected exam periods
        averages = {}
        for exam_id, period in exam_periods.items():
            if period is None:
                averages[exam_id] = None
                continue
            start_month, end_month = period
            relevant_data = attendance_data[(attendance_data['Month'] >= start_month) & (attendance_data['Month'] <= end_month)]
            if not relevant_data.empty:
                avg_attendance = relevant_data['AttendancePercentage'].mean()
                averages[exam_id] = avg_attendance
            else:
                averages[exam_id] = None
    else:
        averages = {int(selected_exam_id): None} if selected_exam_id != 'all' else {1: None, 2: None, 3: None}

    if not averages:
        return jsonify({"error": "No attendance data available."}), 400

    # Load student marks data
    student_data = load_student_data_from_db(conn, student_id, class_id, session_id, section_id, exam_id=selected_exam_id if selected_exam_id != 'all' else None)

    # Extract subject data and plot results
    df, subject_id = extract_student_data(student_data)

    # Determine whether to plot attendance or not based on the user's choice
    plot_attendance = plot_attendance.lower() == 'yes'

    # If 'all' subjects are chosen, plot the average marks for all subjects
    if subject_choice.lower() == 'specific':
        subject_id = data.get('subject_id')
        if not subject_id:
            return jsonify({"error": "Subject ID must be provided when subject_choice is 'specific'."}), 400
        img_base64 = plot_marks_attendance_specific(df, student_id, subject_id, averages, plot_attendance=plot_attendance)
    elif subject_choice.lower() == 'all subject':
        img_base64 = plot_marks_attendance_allsubject(df, student_id, averages, plot_attendance=plot_attendance)
    elif subject_choice.lower() == 'cumulative percentage':
        img_base64 = plot_marks_attendance_cumulative_percentage(df, student_id, averages, plot_attendance=plot_attendance)
    else:
        return jsonify({"error": "Invalid subject_choice. Must be 'all subject', 'cumulative percentage', or 'specific'."}), 400
    
    return jsonify({'graph': img_base64})

    # Close the database connection
    conn.close()
if __name__ == '__main__':
    app.run()
