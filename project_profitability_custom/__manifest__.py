{
    'name': 'Project Profitability',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Measure the real profit margin of each project based on sales, purchases and timesheet costs',
    'description': """
        Extends project.project with real-time profitability margin computation.

        Revenue  : confirmed Sale Orders linked to the project (sale_project).
        Costs    : Vendor Bills + Purchase Orders (linked via analytic account)
                   + Timesheet hours × employee timesheet_cost (hr_timesheet).
        Margin   : (Revenue − Total Costs) / Revenue × 100  [%]

        A colour-coded badge / kanban ribbon categorises each project as:
          • Negative  (< 0 %)
          • Low       (0 – 20 %)
          • Medium    (20 – 50 %)
          • Good      (> 50 %)
    """,
    'author': 'TwenTIC',
    'website': 'https://www.twentic.com',
    'license': 'LGPL-3',
    'depends': [
        'project',
        'sale_project',
        'purchase',
        'hr_timesheet',
    ],
    'data': [
        'views/project_profitability_views.xml',
    ],
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
}
