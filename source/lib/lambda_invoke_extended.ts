#!/usr/bin/env node
/*****************************************************************************
 *  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.   *
 *                                                                            *
 *  Licensed under the Apache License, Version 2.0 (the "License"). You may   *
 *  not use this file except in compliance with the License. A copy of the    *
 *  License is located at                                                     *
 *                                                                            *
 *      http://www.apache.org/licenses/LICENSE-2.0                            *
 *                                                                            *
 *  or in the 'license' file accompanying this file. This file is distributed *
 *  on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,        *
 *  express or implied. See the License for the specific language governing   *
 *  permissions and limitations under the License.                            *
 *****************************************************************************/
import {LambdaInvoke, LambdaInvokeProps} from "@aws-cdk/aws-stepfunctions-tasks";
import {Construct} from "@aws-cdk/core";

export interface LambdaInvokeRSProps extends LambdaInvokeProps {
    readonly resultSelector?: object
}

/**
 * Custom lambda invoker so we can use ResultSelector to filter out all the Lambda Task metadata.
 * See https://github.com/aws/aws-cdk/issues/9904
 */
export class LambdaInvokeRS extends LambdaInvoke {
    private readonly resultSelector?: object

    constructor(scope: Construct, id: string, props: LambdaInvokeRSProps) {
        super(scope, id, props);

        this.resultSelector = props.resultSelector
    }

    public toStateJson(): object {
        const stateJson: any = super.toStateJson();
        if (this.resultSelector !== undefined) {
            stateJson.ResultSelector = this.resultSelector
        }
        return stateJson
    }
}