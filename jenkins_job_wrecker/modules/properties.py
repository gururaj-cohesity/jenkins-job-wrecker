# encoding=utf8
import re
import jenkins_job_wrecker.modules.base
from jenkins_job_wrecker.helpers import get_bool, gen_raw
from jenkins_job_wrecker.modules.triggers import Triggers

PARAMETER_MAPPER = {
    'stringparameterdefinition': 'string',
    'booleanparameterdefinition': 'bool',
    'choiceparameterdefinition': 'choice',
    'textparameterdefinition': 'text',
    'fileparameterdefinition': 'file',
}


class Properties(jenkins_job_wrecker.modules.base.Base):
    component = 'properties'

    def gen_yml(self, yml_parent, data):
        parameters = []
        properties = []
        for child in data:
            object_name = child.tag.split('.')[-1].lower()
            object_name = object_name.replace('-', '').replace('_', '')
            if object_name == 'parametersdefinitionproperty':
                self.registry.dispatch(self.component, 'parameters', child, parameters)
                continue
            elif object_name == 'pipelinetriggersjobproperty':
                # Pipeline scripts put triggers in properties section
                trigger = Triggers(self.registry)
                for grandchild in child:
                    # Find the triggers tag and then generate the yaml
                    if grandchild.tag == 'triggers':
                        trigger.gen_yml(yml_parent, grandchild)
                continue
            self.registry.dispatch(self.component, object_name, child, properties)

        if len(properties) > 0:
            yml_parent.append(['properties', properties])
        if len(parameters) > 0:
            yml_parent.append(['parameters', parameters])


def githubprojectproperty(top, parent):
    github = {}
    for child in top:
        if child.tag == 'projectUrl':
            github['url'] = child.text
        elif child.tag == 'displayName':
            pass
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    parent.append({'github': github})


def envinjectjobproperty(top, parent):
    env_info = {}
    for child in top:
        if child.tag == 'info':
            for grandchild in child:
                if grandchild.tag == 'loadFilesFromMaster':
                    env_info['load-from-master'] = get_bool(grandchild.text)
                elif grandchild.tag == 'groovyScriptContent':
                    if grandchild.text:
                        env_info['groovy-content'] = grandchild.text
                elif grandchild.tag == 'secureGroovyScript':
                    for ggchild in grandchild:
                        if ggchild.tag == 'script':
                            if ggchild.text:
                                env_info['groovy-content'] = ggchild.text
                        elif ggchild.tag == 'sandbox':
                            # No support in jjb for this, fail quietly for
                            # this one
                            pass
                        else:
                            raise NotImplementedError("cannot handle XML %s" % ggchild.tag)
                elif grandchild.tag == 'scriptContent':
                    if grandchild.text:
                        env_info['script-content'] = grandchild.text
                elif grandchild.tag == 'scriptFilePath':
                    if grandchild.text:
                        env_info['script-file'] = grandchild.text
                elif grandchild.tag == 'propertiesContent':
                    if grandchild.text:
                        env_info['properties-content'] = grandchild.text
                elif grandchild.tag == 'propertiesFilePath':
                    if grandchild.text:
                        env_info['properties-file'] = grandchild.text
                else:
                    raise NotImplementedError("cannot handle XML %s" % grandchild.tag)
        elif child.tag == 'on':
            env_info['enabled'] = get_bool(child.text)
        elif child.tag == 'keepJenkinsSystemVariables':
            env_info['keep-system-variables'] = get_bool(child.text)
        elif child.tag == 'keepBuildVariables':
            env_info['keep-build-variables'] = get_bool(child.text)
        elif child.tag == 'overrideBuildParameters':
            env_info['override-build-parameters'] = get_bool(child.text)
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    parent.append({'inject': env_info})


def parameters(top, parent):
    for params in top:
        if params.tag != 'parameterDefinitions':
            raise NotImplementedError("cannot handle XML %s" % params.tag)
        for param in params:
            param_name = param.tag.split('.')[-1].lower()
            if param_name not in PARAMETER_MAPPER:
                gen_raw(param, parent)
                continue
            param_type = PARAMETER_MAPPER[param_name]
            parameter = {}
            for setting in param:
                key = {'defaultValue': 'default'}.get(setting.tag, setting.tag)
                if setting.text is None:
                    parameter[key] = ''
                elif param_type == 'bool' and (setting.text == 'true' or setting.text == 'false'):
                    parameter[key] = (setting.text == 'true')
                elif param_type == 'choice' and setting.tag == 'choices':
                    choices = []
                    for sub_setting in setting:
                        if(sub_setting.attrib['class'] == 'string-array'):
                            for item in sub_setting:
                                choices.append(item.text)
                        else:
                            raise NotImplementedError(sub_setting.attrib['class'])
                    parameter[key] = choices
                else:
                    parameter[key] = setting.text
            parent.append({param_type: parameter})


def throttlejobproperty(top, parent):
    throttle = {}
    for child in top:
        if child.tag == 'maxConcurrentPerNode':
            throttle['max-per-node'] = int(child.text)
        elif child.tag == 'maxConcurrentTotal':
            throttle['max-total'] = int(child.text)
        elif child.tag == 'throttleOption':
            throttle['option'] = child.text
        elif child.tag == 'throttleEnabled':
            throttle['enabled'] = get_bool(child.text)
        elif child.tag == 'categories':
            throttle['categories'] = []
            for grandchild in child:
                if grandchild.tag == "string":
                    throttle['categories'].append(grandchild.text)
        elif child.tag == 'configVersion':
            pass  # assigned by jjb
        elif child.tag == 'limitOneJobWithMatchingParams':
            throttle['parameters-limit'] = child.text
        elif child.tag == 'matrixOptions':
            for grandchild in child:
                if grandchild.tag == "throttleMatrixBuilds":
                    throttle['matrix-builds'] = get_bool(grandchild.text)
                elif grandchild.tag == "throttleMatrixConfigurations":
                    throttle['matrix-configs'] = get_bool(grandchild.text)
        elif child.tag == 'paramsToUseForLimit':
            if child.text:
                throttle['parameters-check-list'] = re.split(r"[\s,]", child.text)
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    parent.append({'throttle': throttle})


def slacknotifierslackjobproperty(top, parent):
    slack = {}
    notifications = {
        "notifySuccess": "notify-success",
        "notifyAborted": "notify-aborted",
        "notifyNotBuilt": "notify-not-built",
        "notifyUnstable": "notify-unstable",
        "notifyFailure": "notify-failure",
        "notifyBackToNormal": "notify-back-to-normal",
        "notifyRepeatedFailure": "notify-repeated-failure"
    }
    for child in top:
        if child.tag == 'teamDomain':
            slack['team-domain'] = child.text
        elif child.tag == 'token':
            slack['token'] = child.text
        elif child.tag == 'room':
            slack['room'] = child.text
        elif child.tag == 'includeTestSummary':
            slack['include-test-summary'] = (child.text == 'true')
        elif child.tag == 'showCommitList':
            slack['show-commit-list'] = (child.text == 'true')
        elif child.tag == 'includeCustomMessage':
            slack['include-custom-message'] = (child.text == 'true')
        elif child.tag == 'customMessage':
            slack['custom-message'] = child.text
        elif child.tag == 'startNotification':
            slack['start-notification'] = (child.text == 'true')
        elif child.tag in notifications:
            slack[notifications[child.tag]] = (child.text == 'true')
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)

    parent.append({'slack': slack})


def builddiscarderproperty(top, parent):
    discarder = {}
    mapping = {'daysToKeep': 'days-to-keep',
               'numToKeep': 'num-to-keep',
               'artifactDaysToKeep': 'artifact-days-to-keep',
               'artifactNumToKeep': 'artifact-num-to-keep'}
    for child in top[0]:
        discarder[mapping[child.tag]] = int(child.text)

    parent.append({'build-discarder': discarder})


def disableconcurrentbuildsjobproperty(top, parent):
    # Pipeline job specific tag.
    # concurrent is false by default anyway, so just going to ignore it
    # Check cli.py root_to_yaml func for more info
    pass


def authorizationmatrixproperty(top, parent):
    # mirror image of: https://opendev.org/jjb/jenkins-job-builder/src/commit/074985c7ff9360bb58be80ffab686746267f814f/jenkins_jobs/modules/properties.py#L530
    credentials = 'com.cloudbees.plugins.credentials.CredentialsProvider.'
    ownership = 'com.synopsys.arc.jenkins.plugins.ownership.OwnershipPlugin.'

    permissions = {
        ''.join((credentials, 'Create')): 'credentials-create',
        ''.join((credentials, 'Delete')): 'credentials-delete',
        ''.join((credentials, 'ManageDomains')): 'credentials-manage-domains',
        ''.join((credentials, 'Update')): 'credentials-update',
        ''.join((credentials, 'View')): 'credentials-view',
        'hudson.model.Item.Build': 'job-build',
        'hudson.model.Item.Cancel': 'job-cancel',
        'hudson.model.Item.Configure': 'job-configure',
        'hudson.model.Item.Create': 'job-create',
        'hudson.model.Item.Delete': 'job-delete',
        'hudson.model.Item.Discover': 'job-discover',
        'hudson.model.Item.ExtendedRead': 'job-extended-read',
        'hudson.model.Item.Move': 'job-move',
        'hudson.model.Item.Read': 'job-read',
        'hudson.model.Item.ViewStatus': 'job-status',
        'hudson.model.Item.Workspace': 'job-workspace',
        ''.join((ownership, 'Jobs')): 'ownership-jobs',
        'hudson.model.Run.Delete': 'run-delete',
        'hudson.model.Run.Replay': 'run-replay',
        'hudson.model.Run.Update': 'run-update',
        'hudson.scm.SCM.Tag': 'scm-tag'
    }
    authorization = {}
    for child in top:
        if child.tag == 'inheritanceStrategy':
            class_ = child.get('class')
            if class_ != 'org.jenkinsci.plugins.matrixauth.inheritance.InheritParentStrategy':
                raise NotImplementedError('cannot handle inheritance strategy - not implemented in JJB')
        elif child.tag == 'permission':
            permission, name = child.text.split(':', 1)
            if name not in authorization:
                authorization[name] = []
            authorization[name].append(permissions[permission])
        else:
            raise NotImplementedError('cannot handle XML {}'.format(child.tag))
    parent.append({'authorization': authorization})


def buildblockerproperty(top, parent):
    build_blocker_property = {}
    for child in top:
        if child.tag == "useBuildBlocker":
            build_blocker_property["use-build-blocker"] = get_bool(child.text)
        elif child.tag == "blockLevel":
            build_blocker_property["block-level"] = child.text
        elif child.tag == "scanQueueFor":
            build_blocker_property["queue-scanning"] = child.text
        elif child.tag == "blockingJobs":
            blocking_jobs = []
            if child.text is not None:
                blocking_jobs = [name.strip() for name in child.text.split('\n')]
            build_blocker_property["blocking-jobs"] = blocking_jobs
    parent.append({'build-blocker': build_blocker_property})


def rebuildsettings(top, parent):
    rebuild = {}
    for child in top:
        if child.tag == 'autoRebuild':
            rebuild['auto-rebuild'] = (child.text == 'true')
        elif child.tag == 'rebuildDisabled':
            rebuild['rebuild-disabled'] = (child.text == 'true')
        else:
            raise NotImplementedError('Unsupported tag')
    parent.append({'rebuild': rebuild})


def diskusageproperty(top, parent):
    parent.append('disk-usage')


def naginatoroptoutproperty(top, parent):
    naginator_opt_out = {}
    for child in top:
        if child.tag == 'optOut':
            naginator_opt_out['opt-out'] = get_bool(child.text)
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)
    parent.append({'naginator-opt-out': naginator_opt_out})


def leastloaddisabledproperty(top, parent):
    least_load = {}
    for child in top:
        if child.tag == 'leastLoadDisabled':
            least_load['disabled'] = get_bool(child.text)
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)
    parent.append({'least-load': least_load})


def ratelimitbranchpropertyjobpropertyimpl(top, parent):
    rate_limit = {}
    for child in top:
        if child.tag == 'durationName':
            rate_limit['time-period'] = child.text
        elif child.tag == 'count':
            rate_limit['number-of-builds'] = int(child.text)
        elif child.tag == 'userBoost':
            rate_limit['skip-rate-limit'] = get_bool(child.text)
        else:
            raise NotImplementedError("cannot handle XML %s" % child.tag)
    parent.append({'branch-api': rate_limit})
