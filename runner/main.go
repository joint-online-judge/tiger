package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"time"

	"github.com/containerd/cgroups"
	"github.com/opencontainers/runtime-spec/specs-go"
)

func main() {
	control, err := cgroups.New(
		cgroups.V1,
		cgroups.StaticPath("/joj.tiger"),
		&specs.LinuxResources{},
	)
	if err != nil {
		panic(err)
	}
	defer control.Delete()
	if len(os.Args) < 2 {
		fmt.Println("usage: main <command>")
		os.Exit(1)
	}
	cmd := exec.Command(os.Args[1], os.Args[2:]...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	start := time.Now()
	err = cmd.Start()
	if err != nil {
		panic(err)
	}
	pid := cmd.Process.Pid
	fmt.Printf("pid: %d\n", pid)
	if err := control.Add(cgroups.Process{Pid: pid}); err != nil {
		panic(err)
	}
	var returnCode int
	exitCode := make(chan int, 1)
	go func(exit_code chan int) {
		if err = cmd.Wait(); err != nil {
			exit_code <- err.(*exec.ExitError).ExitCode()
		} else {
			exit_code <- 0
		}
	}(exitCode)
	timeoutLimit := 1000 * time.Millisecond
	timedOut := false
	select {
	case returnCode = <-exitCode:
	case <-time.After(timeoutLimit):
		fmt.Printf("timeout in %v\n", time.Since(start))
		cmd.Process.Kill()
		returnCode = <-exitCode
		timedOut = true
	}
	stats, _ := control.Stat(cgroups.IgnoreNotExist)
	fmt.Printf("return_code: %d\n", returnCode)
	fmt.Printf("time: %f\n", (float64(stats.CPU.Usage.Total) / 1e9))
	fmt.Printf("memory: %d\n", stats.Memory.Usage.Max) // Memory.Usage.Max = 0 when killed
	fmt.Printf("stdout: %s\n", stdout.String())
	fmt.Printf("stderr: %s\n", stderr.String())
	fmt.Printf("timed_out: %v\n", timedOut)
}
