import csv

_export = True

_print_remaining_hours = True

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


class Grade:
    def __init__(self, grade_number, sections, subjects_day):
        self.grade_number = grade_number  # which grade
        self.sections = sections  # which sections
        self.subjects_day = subjects_day  # which subjects on which day


grades = [
    Grade(
        grade_number=1,
        sections=['A', 'B'],
        subjects_day={
            1: ['English', 'Math', 'Science', 'History'],
            2: ['Art', 'Music', 'Language', 'PE']
        }
    ),
    Grade(
        grade_number=2,
        sections=['A', 'B'],
        subjects_day={
            1: ['English', 'Math', 'Science', 'History'],
            2: ['Art', 'Music', 'Language', 'PE']
        }
    )
]


class Teacher:
    def __init__(self, name, grade_subject_pairs, preferred_class=None, max_hours=24):
        self.name = name  # teacher name
        self.grade_subject_pairs = grade_subject_pairs  # which grades and subjects they can teach
        self.preferred_class = preferred_class  # preferred class they want to teach
        self.max_hours = max_hours  # max hours they can teach


teacher_pool = [
    Teacher("T1", [(1, 'English'), (2, 'English')]),
    Teacher("T2", [(1, 'Math')]),
    Teacher("T3", [(1, 'Science'), (2, 'Science')]),
    Teacher("T4", [(1, 'History'), (2, 'History')]),
    Teacher("T5", [(1, 'Art'), (2, 'Art')]),
    Teacher("T6", [(1, 'Music'), (2, 'Music')]),
    Teacher("T7", [(1, 'Language'), (2, 'Language')]),
    Teacher("T8", [(1, 'PE'), (2, 'PE')]),
    Teacher("T9", [(2, 'Math')]),
]

# finds how many times a particular subject needs to be scheduled for a given grade across all sections and days
required_assignments = {}
for grade in grades:
    for day, day_type in day_schedule_map.items():
        subjects = grade.subjects_day[day_type]
        for subject in subjects:
            key = (grade.grade_number, subject)
            required_assignments[key] = required_assignments.get(key, 0) + len(grade.sections)

# checks if the available teachers can handle the total workload
subject_capacity = {}
for (g_num, subj), needed in required_assignments.items():
    teachers_for_subj = [t for t in teacher_pool if (g_num, subj) in t.grade_subject_pairs]
    total_capacity = sum((t.max_hours // 2) for t in teachers_for_subj)
    subject_capacity[(g_num, subj)] = total_capacity
    if needed > total_capacity:
        if len(teachers_for_subj) == 1:
            t = teachers_for_subj[0]
            print("\nATTENTION: Scheduling Issue Detected!")
            print(f"The subject '{subj}' in Grade {g_num} requires {needed} assignments,")
            print(
                f"but the only qualified teacher '{t.name}' can only handle {t.max_hours // 2} assignments (max {t.max_hours} hours).")
            print("No other teachers are available to cover this subject.")
            print("Please increase this teacher's max hours or add another qualified teacher for this subject.\n")
            exit()
        else:
            print("\nATTENTION: Scheduling Issue Detected!")
            print(f"The subject '{subj}' in Grade {g_num} requires {needed} assignments,")
            print("but even combining all qualified teachers' hours, it's not enough.")
            print("Please adjust max hours or add more qualified teachers for this subject.\n")
            exit()

# check if each teacher can handle their own assignments
teacher_mandatory_load = {}
for (g_num, subj), needed in required_assignments.items():
    teachers_for_subj = [t for t in teacher_pool if (g_num, subj) in t.grade_subject_pairs]
    if len(teachers_for_subj) == 1:
        t = teachers_for_subj[0]
        teacher_mandatory_load[t.name] = teacher_mandatory_load.get(t.name, 0) + needed

# Now check if any teacher's mandatory load exceeds their capacity
for t in teacher_pool:
    if t.name in teacher_mandatory_load:
        mandatory_assignments = teacher_mandatory_load[t.name]
        if mandatory_assignments > (t.max_hours // 2):
            sole_subjects = []
            for (g_num, subj), needed in required_assignments.items():
                teachers_for_subj = [tt for tt in teacher_pool if (g_num, subj) in tt.grade_subject_pairs]
                if len(teachers_for_subj) == 1 and teachers_for_subj[0].name == t.name:
                    sole_subjects.append((g_num, subj, needed))

            print("\nATTENTION: Global Scheduling Issue Detected!")
            print(f"Teacher '{t.name}' is the only teacher qualified for these classes and must cover all assignments:")
            for (g_num, subj, needed) in sole_subjects:
                print(f" - Grade {g_num}, Subject '{subj}': {needed} assignments (needs {needed * 2} hours)")
            print(f"\nTotal mandatory assignments for '{t.name}': {teacher_mandatory_load[t.name]} assignments")
            print(f"But '{t.name}' can only handle {t.max_hours // 2} assignments max (max {t.max_hours} hours).")
            print("There is no alternative teacher to share the load. Please increase max hours for this teacher")
            print("or add another qualified teacher for these subjects.\n")
            exit()

# Now we can start building the CSP, set variables and domains and find any missing teachers
variables = []
domains = {}
missing_teachers = []
for grade in grades:
    for day in day_schedule_map.keys():
        day_type = day_schedule_map[day]
        for section in grade.sections:
            for time_slot in time_slots:
                var_name = f'G{grade.grade_number}_{day}_S{section}_T{time_slot}'
                variables.append(var_name)
                domains[var_name] = []
                for subject in grade.subjects_day[day_type]:
                    eligible_teachers = [t.name for t in teacher_pool if
                                         (grade.grade_number, subject) in t.grade_subject_pairs]
                    if not eligible_teachers:
                        missing_teachers.append((grade.grade_number, subject))
                    else:
                        for teacher_name in eligible_teachers:
                            domains[var_name].append((subject, teacher_name))

# Check for missing teachers and exit if any
if missing_teachers:
    print("Scheduling Error: The following subjects cannot be scheduled due to a lack of teachers:")
    for grade_number, subject in set(missing_teachers):
        print(f"   - Grade {grade_number}: {subject}")
    print("\nPlease assign teachers to these subjects to continue.")
    exit()


def get_teacher_by_name(name):
    for t in teacher_pool:
        if t.name == name:
            return t
    return None


def count_teacher_hours(assignment):
    teacher_hours = {}
    for var, (subject, teacher) in assignment.items():
        teacher_hours[teacher] = teacher_hours.get(teacher, 0) + 2
    return teacher_hours


def constraint1(var, value, assignment, variables, domains):
    subject, teacher = value
    tokens = var.split('_')
    grade_number = int(tokens[0][1])
    day = tokens[1]
    section = tokens[2][1]

    for other_time_slot in time_slots:
        other_var = f'G{grade_number}_{day}_S{section}_T{other_time_slot}'
        if other_var in assignment and other_var != var:
            assigned_subject, assigned_teacher = assignment[other_var]
            if assigned_subject == subject:
                return False, f"Constraint1 Violated: Duplicate subject '{subject}' in Grade {grade_number}, Day {day}, Section {section}."
    return True, ""


def constraint2(var, value, assignment, variables, domains):
    subject, teacher = value
    tokens = var.split('_')
    day = tokens[1]
    time_slot = int(tokens[3][1])

    for v in assignment:
        if v != var:
            v_tokens = v.split('_')
            v_day = v_tokens[1]
            v_time_slot = int(v_tokens[3][1])
            if v_day == day and v_time_slot == time_slot:
                assigned_subject, assigned_teacher = assignment[v]
                if assigned_teacher == teacher:
                    return False, f"Constraint2 Violated: Teacher '{teacher}' assigned to multiple sections at the same time on {day}, Time Slot {time_slot}."
    return True, ""


def constraint3(var, value, assignment, variables, domains):
    subject, teacher = value
    tokens = var.split('_')
    grade_number = int(tokens[0][1])
    day = tokens[1]
    section = tokens[2][1]
    time_slot = int(tokens[3][1])

    for delta in [-1, 1]:
        adjacent_time_slot = time_slot + delta
        if adjacent_time_slot not in time_slots:
            continue
        for other_section in [sec for sec in next(g.sections for g in grades if g.grade_number == grade_number) if
                              sec != section]:
            adj_var = f'G{grade_number}_{day}_S{other_section}_T{adjacent_time_slot}'
            if adj_var in assignment:
                adj_subject, adj_teacher = assignment[adj_var]
                if adj_teacher == teacher:
                    return False, f"Constraint3 Violated: Teacher '{teacher}' has back-to-back assignments in Grade {grade_number}, Day {day}."
    return True, ""


# Check for max hours
def constraint4(var, value, assignment, variables, domains):
    subject, teacher = value
    current_hours = count_teacher_hours(assignment)
    new_hours = current_hours.get(teacher, 0) + 2
    t_obj = get_teacher_by_name(teacher)
    if t_obj is None:
        return False, f"Unknown teacher '{teacher}'"
    if new_hours > t_obj.max_hours:
        return False, f"Max Hours Constraint Violated: Teacher '{teacher}' exceeded max hours ({t_obj.max_hours})."
    return True, ""


constraints = [constraint1, constraint2, constraint3, constraint4]


class CSPEngine:
    def __init__(self, variables, domains, constraints):
        self.variables = variables
        self.domains = domains
        self.constraints = constraints
        self.conflict_log = []

    def is_consistent(self, var, value, assignment):
        conflict_messages = []
        for constraint in self.constraints:
            result, message = constraint(var, value, assignment, self.variables, self.domains)
            if not result:
                conflict_messages.append(message)
        if conflict_messages:
            self.conflict_log.append((var, value, conflict_messages))
            return False
        return True

    def select_unassigned_variable(self, assignment):
        unassigned_vars = [v for v in self.variables if v not in assignment]
        if not unassigned_vars:
            return None
        # MRV heuristic
        return min(unassigned_vars, key=lambda var: len(self.domains[var]))

    def order_domain_values(self, var, assignment):
        return self.domains[var]

    def backtracking_search(self):
        assignment = {}
        result = self._backtrack(assignment)
        if not result:
            return None, self.conflict_log
        return result, None

    def _backtrack(self, assignment):
        if len(assignment) == len(self.variables):
            return assignment

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
            filename_txt = f"Grade{g}_Schedule.txt"
            with open(filename_txt, 'w') as file:
                file.writelines(output_lines)
            print(f"Schedule for Grade {g} has been exported to {filename_txt}.")

            filename_csv = f"Grade{g}_Schedule.csv"
            with open(filename_csv, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(output_data)
            print(f"Schedule for Grade {g} has been exported to {filename_csv}.")
        else:
            print("".join(output_lines))

    if _print_remaining_hours:
        assigned_hours = count_teacher_hours(solution)
        print("Remaining Hours for Each Teacher:")
        for teacher_obj in teacher_pool:
            used_hours = assigned_hours.get(teacher_obj.name, 0)
            remaining = teacher_obj.max_hours - used_hours
            print(f" - {teacher_obj.name}: {remaining} hours remaining")

else:
    print("No solution found.")
    print("Due to the following Reasons:")
    conf_sum = {}
    for var, value, messages in conflicts or []:
        for msg in messages:
            conf_sum[msg] = conf_sum.get(msg, 0) + 1
    for reason, count in conf_sum.items():
        print(f"- {reason} (Occurred {count} times)")

    # Check for max hours violations without alternatives again (final safety check)
    for var, value, messages in conflicts or []:
        for msg in messages:
            if "Max Hours Constraint Violated" in msg:
                subject, teacher = value
                tokens = var.split('_')
                grade_number = int(tokens[0][1])
                var_domain = domains[var]
                same_subject_entries = [t for (subj, t) in var_domain if subj == subject]
                if len(same_subject_entries) == 1 and same_subject_entries[0] == teacher:
                    print("\nATTENTION: Scheduling Issue Detected!")
                    print(
                        f"Teacher '{teacher}' has reached their maximum working hours and cannot be assigned more classes.")
                    print(
                        f"For Grade {grade_number} and Subject '{subject}', there are no alternative teachers available.")
                    print("Please resolve this issue by either increasing the teacher's max hours,")
                    print("or adding another qualified teacher for this subject and grade.")

    print("\nRemaining Hours for Each Teacher (No assignment made):")
    for teacher_obj in teacher_pool:
        print(f" - {teacher_obj.name}: {teacher_obj.max_hours} hours remaining")

def substituteTeacher(teacher, grade, section, timeslot, day, subject):
    allteachList = []
    teacherPool = teacherListMake()
    for t in teacherPool.keys():
        if t != teacher:
            allteachList.append(t)

    for i in range(1, len(grades) + 1):
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

    print(
        f"Substitute teacher {subTeach} assigned to Grade {grade}, Section {section}, Day {day}, Time Slot {timeslot} for Subject {subject}.")

def priortyList(grade, section, subject, timeslot, day, allteachLists):
    teachDict = {}
    checkGrade = makeGradeList(grade)
    for i in allteachLists:
        teachDict[i] = 0
        if i in checkGrade[section]:
            teachDict[i] += 3
        else:
            if checkSubject(subject, i):
                teachDict[i] += 2
        if checkContClass(i, timeslot, day):
            teachDict[i] += 1
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
    print(dictGrade)
    return dictGrade
def checkSubject(subject, teacher_name):
    teacherList = teacherListMake()
    subjects = []
    for i in teacherList.keys():
        for y in teacherList[i]:
            if y[2] not in subjects:
                subjects.append(y[2])
    if subject not in subjects:
        return False
    return True
def checkContClass(teacher, timeslot, day):
    timeslots = numberAssignerTime(timeslot)
    days = numberAssignerDay(day)
    if timeslots == 1:
        checktime = [2]
    elif timeslots == len(time_slots) - 1:
        checktime = [len(time_slots) - 2]
    else:
        checktime = [timeslots - 1, timeslots + 1]
    for i in range(1, len(grades) + 1):
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
def teacherListMake():
    teacherPool = {}
    for i in range(0,13):
        try:
            with open(f'Grade{i}_Schedule.csv', 'r') as file:
                csv_reader = csv.reader(file)
                next(csv_reader)
                for row in csv_reader:
                    section = row[2]  # Section
                    teacher = row[5]
                    grade = row[0]
                    subject = row[4]
                    if teacher not in teacherPool:
                        teacherPool[teacher] = [[grade,section,subject]]
                    else:
                        if [grade,section,subject] not in teacherPool[teacher]:
                            teacherPool[teacher].append([grade,section,subject])
        except:
            continue
    return teacherPool


substituteTeacher('T2', 1, 'A', '11:00am - 1:00pm', 'Monday', 'Math')

