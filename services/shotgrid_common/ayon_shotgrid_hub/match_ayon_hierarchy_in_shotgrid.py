import collections

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from utils import get_sg_entities, get_sg_entity_parent_field, get_sg_entity_as_ay_dict

from nxtools import logging, log_traceback


def match_ayon_hierarchy_in_shotgrid(entity_hub, sg_project, sg_session):
    """Replicate an AYON project into Shotgrid.

    This function creates a "deck" which we keep increasing while traversing
    the AYON project and finding new children, this is more efficient than
    creating a dictionary with the whole AYON project structure since we
    `popleft` the elements when procesing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_session (shotgun_api3.Shotgun): The Shotgrid session.
    """
    logging.info("Getting AYON entities.")
    entity_hub.query_entities_from_server()

    logging.info("Getting Shotgrid entities.")
    sg_entities_by_id, sg_entities_by_parent_id = get_sg_entities(
        sg_session,
        sg_project
    )

    ay_entities_deck = collections.deque()
    sg_project_sync_status = "Synced"

    # Append the project's direct children.
    for ay_project_child in entity_hub._entities_by_parent_id[entity_hub.project_name]:
        ay_entities_deck.append((
            get_sg_entity_as_ay_dict(sg_session, "Project", sg_project["id"]),
            ay_project_child
        ))

    while ay_entities_deck:
        (ay_parent_entity, ay_entity) = ay_entities_deck.popleft()
        logging.debug(f"Processing {ay_entity})")

        sg_entity = None
        if (
            (ay_entity.entity_type == "folder" and ay_entity.folder_type != "Folder")
            or ay_entity.entity_type == "task"
        ):
            sg_entity_id = ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, None)

            if sg_entity_id:
                sg_entity_id = int(sg_entity_id)

                if sg_entity_id in sg_entities_by_id:
                    sg_entity = sg_entities_by_id[sg_entity_id]
                    logging.info(f"Entity already exists in Shotgrid {sg_entity}")

                    if sg_entity[CUST_FIELD_CODE_ID] != ay_entity.id:
                        logging.error("Shotgrid record for AYON id does not match...")
                        try:
                            sg_session.update(
                                sg_entity["shotgridType"],
                                sg_entity["shotgridId"],
                                {
                                    CUST_FIELD_CODE_ID: "",
                                    CUST_FIELD_CODE_SYNC: "Failed"
                                }
                            )
                        except Exception as e:
                            log_traceback(e)
                            sg_project_sync_status = "Failed"

            if sg_entity is None:
                sg_parent_entity = sg_session.find_one(
                    ay_parent_entity["shotgridType"],
                    filters=[["id", "is", ay_parent_entity["shotgridId"]]]
                )
                sg_entity = _create_new_entity(
                    ay_entity,
                    sg_session,
                    sg_project,
                    sg_parent_entity
                )
                sg_entity_id = sg_entity["shotgridId"]
                sg_entities_by_id[sg_entity_id] = sg_entity
                sg_entities_by_parent_id[sg_parent_entity["id"]].append(sg_entity)

            ay_entity.attribs.set(
                SHOTGRID_ID_ATTRIB,
                sg_entity_id
            )
            ay_entity.attribs.set(
                SHOTGRID_TYPE_ATTRIB,
                sg_entity["type"]
            )
            entity_hub.commit_changes()

        if sg_entity is None:
            # Shotgrid doesn't have the concept of "Folders"
            sg_entity = ay_parent_entity

        for ay_entity_child in entity_hub._entities_by_parent_id.get(ay_entity.id, []):
            ay_entities_deck.append((sg_entity, ay_entity_child))

    sg_session.update(
        "Project",
        sg_project["id"],
        {
            CUST_FIELD_CODE_ID: entity_hub.project_name,
            CUST_FIELD_CODE_SYNC: sg_project_sync_status
        }
    )

    entity_hub.project_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_project["id"]
    )

    entity_hub.project_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        "Project"
    )

def _create_new_entity(ay_entity, sg_session, sg_project, sg_parent_entity):
    """Helper method to create entities in Shotgrid.

    Args:
        parent_entity: Ayon parent entity.
        ay_entity (dict): Shotgrid entity to create.
    """

    if ay_entity.entity_type == "task":

        step_query_filters = [["code", "is", ay_entity.task_type]]

        if sg_parent_entity["type"] in ["Asset", "Shot"]:
            step_query_filters.append(
                ["entity_type", "is", sg_parent_entity["type"]]
            )

        task_step = sg_session.find_one(
            "Step",
            filters=step_query_filters,
        )
        if not task_step:
            raise ValueError(
                f"Unable to create Task {ay_entity.task_type} {ay_entity}\n"
                f"    -> Shotgrid is missng Pipeline Step {ay_entity.task_type}"
            )

        new_entity = sg_session.create(
            "Task",
            {
                "project": sg_project,
                "content": ay_entity.label,
                CUST_FIELD_CODE_ID: ay_entity.id,
                CUST_FIELD_CODE_SYNC: "Synced",
                "entity": sg_parent_entity,
                "step": task_step,
            }
        )
    else:
        sg_parent_field = get_sg_entity_parent_field(sg_session, sg_project, ay_entity.folder_type)

        if sg_parent_field == "project" or sg_parent_entity["type"] == "Project":
            new_entity = sg_session.create(
                ay_entity.folder_type,
                {
                    "project": sg_project,
                    "code": ay_entity.name,
                    CUST_FIELD_CODE_ID: ay_entity.id,
                    CUST_FIELD_CODE_SYNC: "Synced",
                }
            )
        else:
            new_entity = sg_session.create(
                ay_entity.folder_type,
                {
                    "project": sg_project,
                    "code": ay_entity.name,
                    CUST_FIELD_CODE_ID: ay_entity.id,
                    CUST_FIELD_CODE_SYNC: "Synced",
                    sg_parent_field: sg_parent_entity,
                }
            )

    logging.debug(f"Created new entity: {new_entity}")
    logging.debug(f"Parent is: {sg_parent_entity}")
    new_entity = get_sg_entity_as_ay_dict(
        sg_session,
        new_entity["type"],
        new_entity["id"]
    )
    return new_entity


