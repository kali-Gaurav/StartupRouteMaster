# Employee Experience Tracking System

This directory contains employee experience files that automatically track work completed by each team member.

## Structure

```
.agent/identity/employees/
├── nova_ml_engineer.md      # ML Engineer - NOVA
├── sigma_backend.md         # Backend Engineer - SIGMA
├── orion_frontend.md        # Frontend Engineer - ORION
├── vault_db.md              # Database Engineer - VAULT
├── vera_analytics.md        # Data Analyst - VERA
├── daedalus_infrastructure.md  # Infrastructure Engineer - DAEDALUS
├── cipher_security.md       # Security Engineer - CIPHER
├── marco_product.md         # Product Manager - MARCO
└── README.md                # This file
```

## How It Works

### Automatic Updates

Employee files are automatically updated when:

1. **Tasks are completed in meetings** - The `employee_experience_updater.py` script reads meeting logs and adds completed tasks to employee experience logs
2. **New meeting logs are added** - Run the updater to process new meetings

### Manual Updates

To manually update employee files, run:

```bash
python .agent/workflows/employee_experience_updater.py
```

### Hook Integration

Two hooks are configured to automatically update employee files:

1. **employee-experience-updater.kiro.hook** - Triggers on file creation
2. **employee-experience-updater-edit.kiro.hook** - Triggers on file edits

Both hooks run the updater when meeting logs in `.agent/logs/` are created or modified.

## Experience Log Format

Each employee file includes an "Experience Log" section that tracks:

- **Date** - When the task was completed
- **Project** - Which project the task belongs to
- **Task** - The specific task completed
- **Impact** - Priority and business impact
- **Hours** - Estimated time spent
- **Tags** - Skills and technologies used

## Example Entry

```markdown
### Design CAT model architecture
**Date:** 2026-05-08  
**Project:** Phase 2 - Contextual Availability Transformer (CAT) Model Planning  
**Impact:** Priority: high
**Hours:** 4h
**Tags:** meeting, task-completion

Completed task as part of Phase 2 - Contextual Availability Transformer (CAT) Model Planning
```

## Updating Employee Files

### For New Employees

1. Create a new file in `.agent/identity/employees/`
2. Use the existing files as templates
3. Add the employee to the `employee_mapping` in `employee_experience_updater.py`

### For New Projects

1. Add tasks to meeting logs or spec files
2. Run the updater to automatically add to employee experience logs

## Related Files

- `.agent/workflows/employee_experience_updater.py` - Main updater script
- `.agent/logs/` - Meeting logs directory
- `.kiro/specs/` - Spec files for task tracking
- `.kiro/hooks/` - Hook configurations

---

**Last Updated:** 2026-05-08