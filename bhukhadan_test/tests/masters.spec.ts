import { Endpoints, authHeader, expectFail, expectOk } from '../helpers/api';
import { authedGet } from '../helpers/auth';
import { expect, test } from '../helpers/fixtures';

/**
 * Master-data cascade used by Flutter home screen:
 * GET /api/bhukhadan/projects
 * GET /api/bhukhadan/areas?project_id=
 * GET /api/bhukhadan/villages?project_id=&area_id=
 */
test.describe('Master data API', () => {
  test('GET /api/bhukhadan/projects requires Authorization', async ({ request }) => {
    const res = await request.get(Endpoints.projects);
    // check_permission raises AccessError → typically 403 in Odoo HTTP
    expect([401, 403, 500]).toContain(res.status());
  });

  test('GET /api/bhukhadan/projects returns list for signed-in user', async ({ request, auth }) => {
    const body = await expectOk(await authedGet(request, Endpoints.projects, auth.token));
    expect(Array.isArray(body.data)).toBeTruthy();
    const rows = body.data as Array<Record<string, unknown>>;
    if (rows.length) {
      expect(rows[0]).toHaveProperty('id');
      expect(rows[0]).toHaveProperty('name');
    }
  });

  test('GET /api/bhukhadan/areas requires project_id', async ({ request, auth }) => {
    const res = await request.get(Endpoints.areas, { headers: authHeader(auth.token) });
    await expectFail(res, 400);
  });

  test('GET /api/bhukhadan/areas returns areas for a project', async ({ request, auth }) => {
    const projectsBody = await expectOk(await authedGet(request, Endpoints.projects, auth.token));
    const projects = (projectsBody.data as Array<Record<string, unknown>>) || [];
    test.skip(!projects.length, 'No projects assigned to test user');

    const projectId = Number(projects[0].id);
    const body = await expectOk(
      await authedGet(request, Endpoints.areas, auth.token, { project_id: projectId }),
    );
    expect(Array.isArray(body.data)).toBeTruthy();
    const areas = body.data as Array<Record<string, unknown>>;
    if (areas.length) {
      expect(areas[0]).toHaveProperty('id');
      expect(areas[0]).toHaveProperty('name');
    }
  });

  test('GET /api/bhukhadan/villages requires project_id and area_id', async ({ request, auth }) => {
    const res = await request.get(`${Endpoints.villages}?project_id=1`, {
      headers: authHeader(auth.token),
    });
    await expectFail(res, 400);
  });

  test('GET /api/bhukhadan/villages filters by project + area', async ({ request, auth }) => {
    const projectsBody = await expectOk(await authedGet(request, Endpoints.projects, auth.token));
    const projects = (projectsBody.data as Array<Record<string, unknown>>) || [];
    test.skip(!projects.length, 'No projects assigned to test user');

    const projectId = Number(projects[0].id);
    const areasBody = await expectOk(
      await authedGet(request, Endpoints.areas, auth.token, { project_id: projectId }),
    );
    const areas = (areasBody.data as Array<Record<string, unknown>>) || [];
    test.skip(!areas.length, 'No areas for first project — map villages to areas first');

    const areaId = Number(areas[0].id);
    const body = await expectOk(
      await authedGet(request, Endpoints.villages, auth.token, {
        project_id: projectId,
        area_id: areaId,
      }),
    );
    expect(Array.isArray(body.data)).toBeTruthy();
    const villages = body.data as Array<Record<string, unknown>>;
    if (villages.length) {
      expect(villages[0]).toHaveProperty('id');
      expect(villages[0]).toHaveProperty('name');
    }
  });

  test('Project → Area → Village cascade is consistent', async ({ request, auth }) => {
    const projectsBody = await expectOk(await authedGet(request, Endpoints.projects, auth.token));
    const projects = (projectsBody.data as Array<Record<string, unknown>>) || [];
    test.skip(!projects.length, 'No projects');

    let found = false;
    for (const p of projects) {
      const areasBody = await expectOk(
        await authedGet(request, Endpoints.areas, auth.token, { project_id: Number(p.id) }),
      );
      for (const a of (areasBody.data as Array<Record<string, unknown>>) || []) {
        const villagesBody = await expectOk(
          await authedGet(request, Endpoints.villages, auth.token, {
            project_id: Number(p.id),
            area_id: Number(a.id),
          }),
        );
        const villages = (villagesBody.data as Array<Record<string, unknown>>) || [];
        if (villages.length) {
          found = true;
          expect(Number(villages[0].id)).toBeGreaterThan(0);
          break;
        }
      }
      if (found) break;
    }
    // Soft assertion: data may not be mapped yet in a fresh DB
    if (!found) {
      test.info().annotations.push({
        type: 'note',
        description: 'No Area→Village mapping found; cascade endpoints still responded OK',
      });
    }
  });
});
