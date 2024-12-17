"""
Innovation 4 Impact CSP Scheduling Algorithm for solving school scheduling challenges.
"""
import csv

# Option to export the schedule to text files or print to console
_export = True  # Set to True to export the schedule to text files and False to print to console

time_slots = {
    1: '9:00am - 11:00am',
    2: '11:00am - 1:00pm',
    3: '1:00pm - 3:00pm',
    4: '3:00pm - 5:00pm'
}

day_schedule_map = {
    'Monday': 1,
    'Tuesday': 2,
    'Wednesday': 1,
    'Thursday': 2,
    'Friday': 1
}

# this is just better
class Grade:
    def __init__(self, grade_number, sections, subjects_day, teacher_subject_map):
        self.grade_number = grade_number
        self.sections = sections
        self.subjects_day = subjects_day
        self.teacher_subject_map = teacher_subject_map
        self.teachers = self.teacher_subject_map.keys()



# grades with their specific sections, subjects, and teachers
grades = [
    Grade(
        grade_number=1,
        sections=['A', 'B'],
        subjects_day={
            1: ['English', 'Math', 'Science', 'History'],
            2: ['Art', 'Music', 'Language', 'PE']
        },
        teacher_subject_map={
            'T1': 'English',
            'T2': 'Math',
            'T3': 'Science',
            'T4': 'History',
            'T5': 'Art',
            'T6': 'Music',
            'T7': 'Language',
            'T8': 'PE'
        }
    ),
    Grade(
        grade_number=2,
        sections=['A', 'B'],
        subjects_day={
            1: ['English', 'Math', 'Science', 'History'],
            2: ['Art', 'Language', 'PE', 'Music']
        },
        teacher_subject_map={
            'T9': 'English',
            'T10': 'Math',
            'T11': 'Science',
            'T12': 'History',
            'T13': 'Art',
            'T14': 'Language',
            'T15': 'PE',
            'T16': 'Music'
        }
    )
]

variables = []
domains = {}
subject_teacher_map = {}
missing_teachers = []

for grade in grades:
    # Build the subject-teacher map for the grade
    subject_teacher_map[grade.grade_number] = {}
    for teacher, subject in grade.teacher_subject_map.items():
        if subject not in subject_teacher_map[grade.grade_number]:
            subject_teacher_map[grade.grade_number][subject] = []
        subject_teacher_map[grade.grade_number][subject].append(teacher)

    # Check for missing teachers
    for day_type, subjects in grade.subjects_day.items():
        for subject in subjects:
            if subject not in subject_teacher_map[grade.grade_number] or not subject_teacher_map[grade.grade_number][
                subject]:
                missing_teachers.append((grade.grade_number, subject))

    # Populate variables and domains for each grade's sections
    for day in day_schedule_map.keys():
        day_type = day_schedule_map[day]
        for section in grade.sections:
            for time_slot in time_slots:
                var_name = f'G{grade.grade_number}_{day}_S{section}_T{time_slot}'
                variables.append(var_name)
                domains[var_name] = []
                for subject in grade.subjects_day[day_type]:
                    if subject in subject_teacher_map[grade.grade_number]:
                        for teacher in subject_teacher_map[grade.grade_number][subject]:
                            domains[var_name].append((subject, teacher))

# Handle missing teachers / subjects
if missing_teachers:
    print("Scheduling Error: The following subjects cannot be scheduled due to a lack of teachers:")
    for grade_number, subject in missing_teachers:
        print(f"   - Grade {grade_number}: {subject}")
    print("\nPlease assign teachers to these subjects to continue.")
    exit()


# Constraints
def constraint1(var, value, assignment, variables, domains):
    """
    Ensures no duplicate subjects in the same section on the same day for the same grade.
    """
    tokens = var.split('_')
    grade_number = int(tokens[0][1])
    day = tokens[1]
    section = tokens[2][1]
    time_slot = int(tokens[3][1])
    subject, teacher = value

    for other_time_slot in time_slots:
        other_var = f'G{grade_number}_{day}_S{section}_T{other_time_slot}'
        if other_var in assignment and other_var != var:
            assigned_subject, assigned_teacher = assignment[other_var]
            if assigned_subject == subject:
                return False, f"Constraint1 Violated: Duplicate subject '{subject}' in Grade {grade_number}, Day {day}, Section {section}."
    return True, ""


def constraint2(var, value, assignment, variables, domains):
    """
    Ensures a teacher is not assigned to teach two classes at the same time, in any grade.
    """
    tokens = var.split('_')
    grade_number = int(tokens[0][1])
    day = tokens[1]
    section = tokens[2][1]
    time_slot = int(tokens[3][1])
    subject, teacher = value

    for grade in grades:
        for other_section in grade.sections:  # Check across all sections in all grades
            other_var = f'G{grade.grade_number}_{day}_S{other_section}_T{time_slot}'
            if other_var in assignment and other_var != var:
                assigned_subject, assigned_teacher = assignment[other_var]
                if assigned_teacher == teacher:
                    return False, f"Constraint2 Violated: Teacher '{teacher}' assigned to multiple sections at the same time on Day {day}, Time Slot {time_slot}."
    return True, ""


def constraint3(var, value, assignment, variables, domains):
    """
    Ensures a teacher does not teach back-to-back time slots within their grade.
    """
    tokens = var.split('_')
    grade_number = int(tokens[0][1])
    day = tokens[1]
    section = tokens[2][1]
    time_slot = int(tokens[3][1])
    subject, teacher = value

    for delta in [-1, 1]:
        adjacent_time_slot = time_slot + delta
        if adjacent_time_slot not in time_slots:
            continue
        for other_section in grades[grade_number - 1].sections:
            adj_var = f'G{grade_number}_{day}_S{other_section}_T{adjacent_time_slot}'
            if adj_var in assignment:
                adj_subject, adj_teacher = assignment[adj_var]
                if adj_teacher == teacher:
                    return False, f"Constraint3 Violated: Teacher '{teacher}' has back-to-back assignments in Grade {grade_number}, Day {day}, Time Slot {time_slot}."
    return True, ""


constraints = [constraint1, constraint2, constraint3]


# CSPEngine - Our custom Constraint Satisfaction Problem solver
class CSPEngine:
    def __init__(self, variables, domains, constraints):
        self.variables = variables
        self.domains = domains
        self.constraints = constraints
        self.conflict_log = []  # To store conflict reasons

    def is_consistent(self, var, value, assignment):
        conflict_messages = []
        for constraint in self.constraints:
            result, message = constraint(var, value, assignment, self.variables, self.domains)
            if not result:
                conflict_messages.append(message)
        if conflict_messages:
            # Store the conflicts for reporting
            self.conflict_log.append((var, value, conflict_messages))
            return False
        return True

    def select_unassigned_variable(self, assignment):
        # MRV (Minimum Remaining Values) heuristic
        unassigned_vars = [v for v in self.variables if v not in assignment]
        # Select the variable with the smallest domain
        if not unassigned_vars:
            return None
        mrv_var = min(unassigned_vars, key=lambda var: len(self.domains[var]))
        return mrv_var

    def order_domain_values(self, var, assignment):
        # LCV (Least Constraining Value) heuristic can be implemented here later
        return self.domains[var]

    def backtracking_search(self):
        assignment = {}
        result = self._backtrack(assignment)
        if not result:
            # If no solution, return conflict log
            return None, self.conflict_log
        return result, None

    def _backtrack(self, assignment):
        if len(assignment) == len(self.variables):
            return assignment  # Solution exists

        var = self.select_unassigned_variable(assignment)
        if var is None:
            return None

        for value in self.order_domain_values(var, assignment):
            if self.is_consistent(var, value, assignment):
                assignment[var] = value
                result = self._backtrack(assignment)
                if result:
                    return result
                del assignment[var]
        return None


csp_engine = CSPEngine(variables, domains, constraints)
solution, conflicts = csp_engine.backtracking_search()

if solution:
    schedule = {}
    for var, value in solution.items():
        subject, teacher = value
        tokens = var.split('_')
        g = int(tokens[0][1])
        day = tokens[1]
        s = tokens[2][1]
        t = int(tokens[3][1])
        if g not in schedule:
            schedule[g] = {}
        if day not in schedule[g]:
            schedule[g][day] = {}
        if s not in schedule[g][day]:
            schedule[g][day][s] = {}
        schedule[g][day][s][t] = (subject, teacher)

    for g in sorted(schedule.keys()):
        output_lines = [f"Grade {g} Weekly Schedule:\n"]
        output_data = [["Grade", "Day", "Section", "Time Slot", "Subject", "Teacher"]]
        for day in day_schedule_map.keys():
            output_lines.append(f"{day}:\n")
            d = day_schedule_map[day]
            grade_sections = next(grade.sections for grade in grades if grade.grade_number == g)
            for s in grade_sections:
                output_lines.append(f"  Section {s}:\n")
                for t in sorted(time_slots):
                    time_range = time_slots[t]
                    if t in schedule[g][day][s]:
                        subject, teacher = schedule[g][day][s][t]
                        output_lines.append(f"    {time_range}: {subject} (Teacher: {teacher})\n")
                        output_data.append([g, day, s, time_range, subject, teacher])
                    else:
                        output_lines.append(f"    {time_range}: Free Period\n")
                        output_data.append([g, day, s, time_range, "Free Period", "N/A"])
            output_lines.append("\n")
        if _export:
            # Export to text file
            filename_txt = f"Grade{g}_Schedule.txt"
            with open(filename_txt, 'w') as file:
                file.writelines(output_lines)
            print(f"Schedule for Grade {g} has been exported to {filename_txt}.")

            # Export to CSV file
            filename_csv = f"Grade{g}_Schedule.csv"
            with open(filename_csv, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(output_data)
            print(f"Schedule for Grade {g} has been exported to {filename_csv}.")
        else:
            print("".join(output_lines))
else:
    print("No solution found.")
    print("Due to the following Reasons:")
    conf_sum = {}
    for var, value, messages in conflicts:
        for msg in messages:
            if msg in conf_sum:
                conf_sum[msg] += 1
            else:
                conf_sum[msg] = 1
    for reason, count in conf_sum.items():
        print(f"- {reason} (Occurred {count} times)")


def substituteTeacher(teacher, grade, section, timeslot, day, subject):
    allteachList = []
    for i in grades:
        for y in i.teachers:
            if y not in allteachList and y != teacher:
                allteachList.append(y)
    for i in range(1, len(grades)+1):
        with open(f'Grade{i}_Schedule.csv', 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)
            for row in csv_reader:
                if numberAssignerDay(row[1]) == numberAssignerDay(day):
                    if numberAssignerTime(row[3]) == numberAssignerTime(timeslot):
                        if row[5] in allteachList:
                            allteachList.remove(row[5])
    teachDict = priortyList(grade, section, subject, timeslot, day, allteachList)
    max_priority = 0
    subTeach = ''
    for i in teachDict.keys():
        if max_priority < teachDict[i]:
            max_priority = teachDict[i]
            subTeach = i

    # Modify the Grade CSV file with the substitute teacher
    csv_file = f'Grade{grade}_Schedule.csv'
    updated_rows = []

    with open(csv_file, 'r') as file:
        csv_reader = csv.reader(file)
        header = next(csv_reader)  # Save the header row
        updated_rows.append(header)
        for row in csv_reader:
            # Check if the row matches the specified section, timeslot, and day
            if row[2] == section and row[3] == timeslot and row[1] == day:
                # Update the teacher and subject
                row[5] = subTeach
                row[4] = subject
            updated_rows.append(row)
    
    # Write the updated rows back to the CSV file
    with open(csv_file, 'w', newline='') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerows(updated_rows)

    print(f"Substitute teacher {subTeach} assigned to Grade {grade}, Section {section}, Day {day}, Time Slot {timeslot} for Subject {subject}.")

# Rest of the code remains unchanged

    

def priortyList(grade, section, subject, timeslot, day, allteachLists):
    teachDict = {}
    checkGrade = makeGradeList(grade)
    for i in allteachLists:
        teachDict[i] = 0
        if i in checkGrade[section]:
            teachDict[i]+=3
        else:
            if checkSubject(subject, i):
                teachDict[i]+=2
        if checkContClass(i,timeslot, day):
            teachDict[i]+=1
    return teachDict
        
def makeGradeList(grade):
    dictGrade = {}
    with open(f'Grade{grade}_Schedule.csv', 'r') as file:
        csv_reader = csv.reader(file)
        next(csv_reader)  # Skip the header row
        for row in csv_reader:
            section = row[2]  # Section
            teacher = row[5]  # Teacher
            if section not in dictGrade:
                dictGrade[section] = []
            if teacher not in dictGrade[section]:
                dictGrade[section].append(teacher)
    return dictGrade

def checkSubject(subject, teacher):
    for i in grades:
        maping = i.teacher_subject_map
        for y in maping.keys():
            if y == teacher:
                if maping[y] == subject:
                    return True
    return False
def checkContClass(teacher, timeslot, day):
    timeslots = numberAssignerTime(timeslot)
    days = numberAssignerDay(day)
    if timeslots == 1:
        checktime = [2]
    elif timeslots == len(time_slots)-1:
        checktime = [len(time_slots)-2]
    else:
        checktime = [timeslots-1,timeslots+1]
    for i in range(1,len(grades)+1):
        with open(f'Grade{i}_Schedule.csv', 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)
            for row in csv_reader:
                if numberAssignerDay(row[1]) == days:
                    if (numberAssignerTime(row[3]) in checktime) and (row[5] == teacher):
                        return False
    return True


def numberAssignerDay(day):
    days = day_schedule_map[day]
    return days
def numberAssignerTime(timeslot):
    for i in time_slots:
        if time_slots[i] == timeslot:
            return i
substituteTeacher('T1', 1, 'A', '9:00am - 11:00am', 'Monday','English')
#1,Monday,A,9:00am - 11:00am,English,T1