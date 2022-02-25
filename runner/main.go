package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"os/user"
	"strconv"
	"syscall"
	"time"

	"github.com/containerd/cgroups"
	"github.com/opencontainers/runtime-spec/specs-go"
	"github.com/vmihailenco/msgpack/v5"
)

type CompletedCommand struct {
	ReturnCode int
	Stdout     []byte
	Stderr     []byte
	TimedOut   bool
	Time       uint64
	Memory     uint64
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("usage: main <command>")
		os.Exit(1)
	}
	u, err := user.Lookup(os.Getenv("SUDO_USER"))
	if err != nil {
		panic(err)
	}
	timeoutMs := 1000
	control, err := cgroups.New(
		cgroups.V1,
		cgroups.StaticPath("/joj.tiger"),
		&specs.LinuxResources{},
	)
	if err != nil {
		panic(err)
	}
	defer control.Delete()
	cmd := exec.Command(os.Args[1], os.Args[2:]...)
	cmd.SysProcAttr = &syscall.SysProcAttr{}
	// run command as non-root
	uid, _ := strconv.ParseUint(u.Uid, 10, 32)
	gid, _ := strconv.ParseUint(u.Gid, 10, 32)
	cmd.SysProcAttr.Credential = &syscall.Credential{Uid: uint32(uid), Gid: uint32(gid)}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	start := time.Now()
	err = cmd.Start()
	if err != nil {
		panic(err)
	}
	pid := cmd.Process.Pid
	fmt.Fprintf(os.Stderr, "pid: %d\n", pid)
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
	timeoutLimit := time.Duration(timeoutMs) * time.Millisecond
	timedOut := false
	select {
	case returnCode = <-exitCode:
		fmt.Fprintf(os.Stderr, "status: done in %v\n", time.Since(start))
	case <-time.After(timeoutLimit):
		fmt.Fprintf(os.Stderr, "status: timeout in %v\n", time.Since(start))
		cmd.Process.Kill()
		returnCode = <-exitCode
		timedOut = true
	}
	stats, _ := control.Stat(cgroups.IgnoreNotExist)
	fmt.Fprintf(os.Stderr, "return_code: %d\n", returnCode)
	fmt.Fprintf(os.Stderr, "time: %d\n", stats.CPU.Usage.Total)
	fmt.Fprintf(os.Stderr, "memory: %d\n", stats.Memory.Usage.Max) // Memory.Usage.Max = 0 when killed
	fmt.Fprintf(os.Stderr, "stdout: %s\n", stdout.String())
	fmt.Fprintf(os.Stderr, "stderr: %s\n", stderr.String())
	fmt.Fprintf(os.Stderr, "timed_out: %v\n", timedOut)
	completedCommand := CompletedCommand{
		ReturnCode: returnCode,
		Stdout:     stdout.Bytes(),
		Stderr:     stderr.Bytes(),
		TimedOut:   timedOut,
		Time:       stats.CPU.Usage.Total,
		Memory:     stats.Memory.Usage.Max,
	}
	b, err := msgpack.Marshal(&completedCommand)
	if err != nil {
		panic(err)
	}
	fmt.Printf("%v\n", string(b))
}
