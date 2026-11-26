from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page
from app.modules.departments.dependencies import get_department_service
from app.modules.employees.dependencies import get_employee_service
from app.modules.job_titles.dependencies import get_job_title_service
from app.modules.positions.dependencies import get_position_service
from app.seed.data import DEPARTMENTS, PEOPLE


async def _all_items[T](fetch: Callable[[str | None], Awaitable[Page[T]]]) -> AsyncIterator[T]:
    """Recorre todas las páginas de un listado, siguiendo el cursor."""
    after = None
    while True:
        page = await fetch(after)
        for item in page.items:
            yield item
        if page.next_cursor is None:
            return
        after = page.next_cursor


async def seed(session: AsyncSession) -> int:
    """Crea lo que falte y devuelve cuántos empleados nuevos hay. No hace commit."""
    # Fuera de un request no hay Depends(): las fábricas se llaman como funciones normales.
    job_titles = get_job_title_service(session)
    departments = get_department_service(session)
    employees = get_employee_service(session)
    positions = get_position_service(session)

    # Se incluyen los inactivos: sus nombres y emails también están ocupados.
    # is_active=None (omitido) devuelve activos e inactivos.
    title_ids = {title.name: title.id for title in await job_titles.list_all()}
    department_ids = {
        d.name: d.id
        async for d in _all_items(
            lambda after: departments.list_page(q=None, sort="name", order="asc", after=after)
        )
    }
    employee_ids = {
        employee.email: employee.id
        async for employee in _all_items(
            lambda after: employees.list_page(
                is_active=None,
                email=None,
                q=None,
                department_id=None,
                manager_id=None,
                has_manager=None,
                job_title_id=None,
                sort="last_name",
                order="asc",
                after=after,
            )
        )
    }

    for name in {p.title for person in PEOPLE for p in person.positions} - title_ids.keys():
        title_ids[name] = (await job_titles.create(name=name, description=None)).id

    # El encargado se asigna al final: los empleados aún no existen.
    new_departments = [name for name in DEPARTMENTS if name not in department_ids]
    for name in new_departments:
        department_ids[name] = (await departments.create(name=name, manager_id=None)).id

    created = 0
    for person in PEOPLE:
        if person.email in employee_ids:
            continue
        employee = await employees.create(
            first_name=person.first_name,
            last_name=person.last_name,
            email=person.email,
            phone=None,
            hire_date=date.fromisoformat(person.positions[0].start),
            manager_id=employee_ids[person.manager] if person.manager else None,
            department_id=department_ids[person.department],
        )
        employee_ids[person.email] = employee.id
        # Cada asignación cierra la anterior, igual que en POST /positions.
        for position in person.positions:
            await positions.assign(
                employee.id,
                job_title_id=title_ids[position.title],
                salary=Decimal(position.salary),
                start_date=date.fromisoformat(position.start),
                notes=None,
            )
        created += 1

    for name in new_departments:
        await departments.update(
            department_ids[name], {"manager_id": employee_ids[DEPARTMENTS[name]]}
        )
    return created
