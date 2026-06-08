#!/usr/bin/env python3
"""
Employee Experience Updater

This script automatically updates employee files in .agent/identity/employees/
when tasks are completed or when employees contribute to projects.

It reads meeting logs and updates employee experience records.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class TaskStatus(Enum):
    """Task status enumeration."""
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"


@dataclass
class ExperienceEntry:
    """Represents a single experience entry for an employee."""
    date: str
    project: str
    task: str
    description: str
    impact: str
    hours_spent: Optional[int] = None
    status: str = "Completed"
    tags: List[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        impact_str = f"**Impact:** {self.impact}" if self.impact else ""
        hours_str = f"**Hours:** {self.hours_spent}h" if self.hours_spent else ""
        tags_str = f"**Tags:** {', '.join(self.tags)}" if self.tags else ""
        
        return f"""
### {self.task}
**Date:** {self.date}  
**Project:** {self.project}  
{impact_str}
{hours_str}
{tags_str}

{self.description}
"""


@dataclass
class EmployeeExperience:
    """Represents the experience record for an employee."""
    employee_id: str
    name: str
    role: str
    experiences: List[ExperienceEntry] = field(default_factory=list)
    total_hours: int = 0
    projects_completed: List[str] = field(default_factory=list)
    skills_acquired: List[str] = field(default_factory=list)
    
    def add_experience(self, experience: ExperienceEntry):
        """Add a new experience entry."""
        self.experiences.append(experience)
        self.total_hours += experience.hours_spent or 0
        if experience.project not in self.projects_completed:
            self.projects_completed.append(experience.project)
        for tag in experience.tags:
            if tag not in self.skills_acquired:
                self.skills_acquired.append(tag)
    
    def to_markdown(self) -> str:
        """Convert to markdown format."""
        experiences_section = ""
        for exp in self.experiences:
            experiences_section += exp.to_markdown()
        
        return f"""
## 📚 Experience Log

### Summary
- **Total Experience Entries:** {len(self.experiences)}
- **Total Hours Spent:** {self.total_hours}h
- **Projects Completed:** {', '.join(self.projects_completed)}
- **Skills Acquired:** {', '.join(self.skills_acquired)}

### Experience Entries
{experiences_section}
"""


class EmployeeExperienceUpdater:
    """Updates employee experience files based on meeting logs and task completion."""
    
    def __init__(self):
        """Initialize the updater."""
        self.base_path = Path(".agent")
        self.employees_path = self.base_path / "identity" / "employees"
        self.logs_path = self.base_path / "logs"
        
        # Employee ID mapping
        self.employee_mapping = {
            "NOVA": "nova_ml_engineer.md",
            "SIGMA": "sigma_backend.md",
            "ORION": "orion_frontend.md",
            "VAULT": "vault_db.md",
            "VERA": "vera_analytics.md",
            "DAEDALUS": "daedalus_infrastructure.md",
            "CIPHER": "cipher_security.md",
            "MARCO": "marco_product.md",
        }
        
        # Track updated employees
        self.updated_employees: Dict[str, List[str]] = {}
    
    def load_meeting_log(self, log_file: str) -> Dict[str, Any]:
        """Load a meeting log file."""
        log_path = self.logs_path / log_file
        with open(log_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_tasks_from_meeting(self, meeting_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tasks from meeting transcript."""
        tasks = []
        
        # Extract tasks from transcript
        for entry in meeting_data.get("transcript", []):
            for task in entry.get("tasks", []):
                task["speaker"] = entry.get("speaker", "Unknown")
                task["round"] = entry.get("round", 0)
                tasks.append(task)
        
        return tasks
    
    def update_employee_file(self, employee_name: str, experience: ExperienceEntry) -> bool:
        """Update an employee's experience file."""
        employee_file = self.employee_mapping.get(employee_name)
        if not employee_file:
            print(f"Warning: No employee file found for {employee_name}")
            return False
        
        employee_path = self.employees_path / employee_file
        
        if not employee_path.exists():
            print(f"Warning: Employee file not found: {employee_path}")
            return False
        
        # Read existing file
        with open(employee_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create experience section
        experience_section = experience.to_markdown()
        
        # Find or create experience section
        if "## 📚 Experience Log" in content:
            # Replace existing experience section
            pattern = r"## 📚 Experience Log.*?(?=##|$)"
            content = re.sub(pattern, f"## 📚 Experience Log\n{experience_section}", content, flags=re.DOTALL)
        else:
            # Add experience section before "## 🔗 Related Documents"
            if "## 🔗 Related Documents" in content:
                content = content.replace(
                    "## 🔗 Related Documents",
                    f"## 📚 Experience Log\n{experience_section}\n\n## 🔗 Related Documents"
                )
            else:
                content += f"\n\n## 📚 Experience Log\n{experience_section}"
        
        # Update last updated date
        today = datetime.now().strftime("%Y-%m-%d")
        content = re.sub(
            r"\*\*Last Updated:\*\*.*",
            f"**Last Updated:** {today}",
            content
        )
        
        # Write updated content
        with open(employee_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Updated {employee_name}'s experience file")
        
        # Track update
        if employee_name not in self.updated_employees:
            self.updated_employees[employee_name] = []
        self.updated_employees[employee_name].append(experience.task)
        
        return True
    
    def process_meeting(self, meeting_file: str) -> Dict[str, Any]:
        """Process a meeting log and update employee files."""
        print(f"\nProcessing meeting: {meeting_file}")
        
        meeting_data = self.load_meeting_log(meeting_file)
        tasks = self.extract_tasks_from_meeting(meeting_data)
        
        print(f"Found {len(tasks)} tasks in meeting")
        
        for task in tasks:
            assignee = task.get("assignee", "Unknown")
            task_title = task.get("title", "Unknown Task")
            priority = task.get("priority", "medium")
            
            # Create experience entry
            experience = ExperienceEntry(
                date=datetime.now().strftime("%Y-%m-%d"),
                project=meeting_data.get("topic", "Unknown Project"),
                task=task_title,
                description=f"Completed task as part of {meeting_data.get('topic', 'meeting')}",
                impact=f"Priority: {priority}",
                hours_spent=4,  # Estimate 4 hours per task
                tags=["meeting", "task-completion"],
                status="Completed"
            )
            
            # Update employee file
            self.update_employee_file(assignee, experience)
        
        return {
            "meeting": meeting_file,
            "tasks_processed": len(tasks),
            "employees_updated": list(self.updated_employees.keys())
        }
    
    def process_all_meetings(self) -> List[Dict[str, Any]]:
        """Process all meeting logs."""
        results = []
        
        # Find all meeting logs
        meeting_files = list(self.logs_path.glob("*.json"))
        
        for meeting_file in meeting_files:
            result = self.process_meeting(meeting_file.name)
            results.append(result)
        
        return results
    
    def generate_summary(self, results: List[Dict[str, Any]]) -> str:
        """Generate a summary of updates."""
        summary = []
        summary.append("=" * 80)
        summary.append("EMPLOYEE EXPERIENCE UPDATER - SUMMARY")
        summary.append("=" * 80)
        
        total_tasks = sum(r["tasks_processed"] for r in results)
        total_employees = len(set(
            emp for r in results for emp in r["employees_updated"]
        ))
        
        summary.append(f"\nTotal Tasks Processed: {total_tasks}")
        summary.append(f"Total Employees Updated: {total_employees}")
        
        summary.append("\nUpdates by Employee:")
        for employee, tasks in self.updated_employees.items():
            summary.append(f"  - {employee}: {len(tasks)} tasks")
        
        summary.append("\n" + "=" * 80)
        
        return "\n".join(summary)


def main():
    """Main entry point."""
    print("=" * 80)
    print("EMPLOYEE EXPERIENCE UPDATER")
    print("=" * 80)
    
    # Create updater
    updater = EmployeeExperienceUpdater()
    
    # Process all meetings
    results = updater.process_all_meetings()
    
    # Generate and print summary
    summary = updater.generate_summary(results)
    print(summary)
    
    return updater, results


if __name__ == "__main__":
    main()