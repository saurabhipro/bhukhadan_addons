{
    'name': 'Bhuarjan CBA Core',
    'version': '18.0.3.1.0',
    'summary': 'Coal Bearing Areas Act — standalone L&R Master SOP with BPMN designer.',
    'sequence': 5,
    'description': """
Standalone Coal Bearing Areas Act (CBA) land acquisition workflow for SECL L&R operations.
Does not require the Bhuarjan (RFCTLARR) module. Includes own project/location masters,
case workflow driven by the SECL L and R Master SOP BPMN diagram, step photos, and
interactive process map viewer.
    """,
    'category': 'Coal Bearing Act',
    'website': 'bhuarjan.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/cba_security.xml',
        'security/ir.model.access.csv',
        'data/cba_sequence.xml',
        'data/cba_master_demo_data.xml',
        'data/cba_photo_type_data.xml',
        'data/cba_workflow_steps.xml',
        'data/cba_workflow_default.xml',
        'data/cba_bpmn_definition.xml',
        'views/cba_master_views.xml',
        'views/cba_workflow_step_views.xml',
        'views/cba_workflow_designer_views.xml',
        'views/cba_case_views.xml',
        'views/cba_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bhuarjan_cba_core/static/src/scss/bpmn_viewer.scss',
            'bhuarjan_cba_core/static/src/components/bpmn_canvas_utils.js',
            'bhuarjan_cba_core/static/src/components/bpmn_viewer/bpmn_viewer.xml',
            'bhuarjan_cba_core/static/src/components/bpmn_viewer/bpmn_viewer.js',
            'bhuarjan_cba_core/static/src/components/bpmn_modeler/bpmn_modeler.xml',
            'bhuarjan_cba_core/static/src/components/bpmn_modeler/bpmn_modeler.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
}
